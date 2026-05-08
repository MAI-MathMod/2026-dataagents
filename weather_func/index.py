import json
import os

import requests


def _extract_city(event):
    if isinstance(event, dict):
        if "city" in event:
            return event["city"]

        body = event.get("body")
        if isinstance(body, str) and body:
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                return body
        if isinstance(body, dict):
            return body.get("city")

    return None


def handler(event, context):
    city = _extract_city(event) or "Moscow"
    appid = os.environ["openweathermap_appid"]

    response = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": city, "appid": appid, "units": "metric", "lang": "ru"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    result = {
        "city": data.get("name", city),
        "temperature_c": data["main"]["temp"],
        "feels_like_c": data["main"]["feels_like"],
        "humidity_percent": data["main"]["humidity"],
        "description": data["weather"][0]["description"],
        "wind_m_s": data["wind"]["speed"],
    }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(result, ensure_ascii=False),
    }
