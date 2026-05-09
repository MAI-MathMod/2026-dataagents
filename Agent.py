"""
Universal Agent Class for Yandex Cloud Responses API

Поддерживает различные типы инструментов:
- Pydantic-классы: локальные функции с методом process(session_id)
- JSON-словари: web_search, file_search, mcp, function

Использование:
    from Agent import Agent
    agent = Agent(client, instruction="...", tools=[...])
    result = agent("Привет!")
"""

import os
import json
from typing import List, Union, Dict, Any
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv


class Agent:
    """
    Универсальный агент с поддержкой Function Calling.
    
    Поддерживает смешанный список инструментов:
    - Pydantic-классы — локальные функции с методом process(session_id)
    - JSON-словари:
        - type: "web_search" — поиск в интернете
        - type: "file_search" — поиск по файлам (векторный индекс)
        - type: "mcp" — Model Context Protocol сервер
        - type: "function" — описание функции
    
    Примеры инструментов:
    
    # Web Search
    {"type": "web_search", "search_context_size": "medium"}
    
    # File Search (RAG)
    {"type": "file_search", "vector_store_ids": ["vs_xxx"], "max_num_results": 5}
    
    # MCP
    {"type": "mcp", "server_url": "http://...", "server_label": "Name", "require_approval": "never"}
    
    # Pydantic (локальная функция)
    class MyTool(BaseModel):
        param: str
        def process(self, session_id): return "result"
    """
    
    def __init__(
        self, 
        client: OpenAI,
        instruction: str,
        tools: List[Union[type, Dict[str, Any]]] = None,
        model: str = None,
        tool_choice: str = "auto",
        verbose: bool = True
    ):
        """
        Args:
            client: OpenAI-клиент (создать через create_client())
            instruction: Системный промпт для агента
            tools: Список инструментов (Pydantic-классы или JSON-словари)
            model: URI модели
            tool_choice: auto | required | none
            verbose: Выводить ли отладочную информацию
        """
        self.client = client
        self.instruction = instruction
        self.model = model
        self.tool_choice = tool_choice
        self.verbose = verbose
        
        # Разделяем инструменты
        self.tools = []          # Для отправки в API
        self.tool_map = {}       # Pydantic: имя -> класс
        
        for tool in (tools or []):
            if isinstance(tool, dict):
                # JSON (web_search, file_search, mcp, function)
                self.tools.append(tool)
            elif isinstance(tool, type) and issubclass(tool, BaseModel):
                # Pydantic — конвертируем в JSON schema
                self.tool_map[tool.__name__] = tool
                self.tools.append({
                    "type": "function",
                    "name": tool.__name__,
                    "description": tool.__doc__ or "",
                    "parameters": tool.model_json_schema(),
                })
        
        # Сессии пользователей
        self.user_sessions = {}
    
    def _log(self, message: str):
        """Вывод отладочной информации."""
        if self.verbose:
            print(message)
    
    def __call__(self, message: str, session_id: str = "default") -> Any:
        """
        Обработка сообщения пользователя.
        
        Args:
            message: Текст сообщения
            session_id: ID сессии (для multi-user)
        
        Returns:
            Объект Response от API
        """
        s = self.user_sessions.get(session_id, {"last_reply_id": None, "history": []})
        s["history"].append({"role": "user", "content": message})
        
        # Первый запрос
        res = self.client.responses.create(
            model=self.model,
            store=True,
            tools=self.tools if self.tools else None,
            tool_choice=self.tool_choice if self.tools else None,
            instructions=self.instruction,
            previous_response_id=s["last_reply_id"],
            input=message
        )
        
        # Цикл обработки (до 10 итераций)
        for _ in range(10):
            # Проверяем локальные function calls (Pydantic)
            tool_calls = [item for item in res.output if item.type == "function_call"]
            if tool_calls:
                out = []
                for call in tool_calls:
                    if call.name in self.tool_map:
                        args_str = call.arguments[:50] + "..." if len(call.arguments or "") > 50 else call.arguments
                        self._log(f"  🔧 {call.name}({args_str})")
                        try:
                            fn = self.tool_map[call.name]
                            if call.arguments:
                                obj = fn.model_validate(json.loads(call.arguments))
                            else:
                                obj = fn()
                            result = obj.process(session_id)
                        except Exception as e:
                            result = f"Ошибка: {e}"
                        out.append({
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": str(result)
                        })
                
                if out:
                    res = self.client.responses.create(
                        model=self.model,
                        input=out,
                        tools=self.tools,
                        previous_response_id=res.id,
                        store=True
                    )
                    continue
            
            # Проверяем MCP approval requests
            mcp_approve = [item for item in res.output if item.type == "mcp_approval_request"]
            if mcp_approve:
                self._log(f"  📡 MCP: автоматическое подтверждение {len(mcp_approve)} запросов")
                res = self.client.responses.create(
                    model=self.model,
                    previous_response_id=res.id,
                    tools=self.tools,
                    input=[{
                        "type": "mcp_approval_response",
                        "approve": True,
                        "approval_request_id": m.id
                    } for m in mcp_approve]
                )
                continue
            
            # Нет больше вызовов — выходим
            break
        
        # Сохраняем состояние
        s["last_reply_id"] = res.id
        s["history"].append({"role": "assistant", "content": res.output_text})
        self.user_sessions[session_id] = s
        
        return res
    
    def history(self, session_id: str = "default") -> list:
        """Возвращает историю переписки для сессии."""
        return self.user_sessions.get(session_id, {}).get("history", [])
    
    def reset(self, session_id: str = "default"):
        """Сбрасывает историю сессии."""
        if session_id in self.user_sessions:
            del self.user_sessions[session_id]
