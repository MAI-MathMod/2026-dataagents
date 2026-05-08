param(
    [string]$FunctionName = "ai-studio-weather-demo",
    [string]$GatewayName = "weather-demo-mcp",
    [string]$FolderId = $env:folder_id,
    [string]$ServiceAccountId = $env:service_account_id,
    [string]$OpenWeatherMapAppId = $env:openweathermap_appid
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    $envPath = Join-Path $PSScriptRoot "..\.env"
    $values = @{}
    if (-not (Test-Path $envPath)) { return $values }

    foreach ($line in Get-Content $envPath) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }

        $name, $value = $trimmed.Split("=", 2)
        $values[$name.Trim()] = $value.Trim().Trim('"').Trim("'")
    }

    return $values
}

$dotEnv = Read-DotEnv

if ($dotEnv.ContainsKey("folder_id")) { $FolderId = $dotEnv["folder_id"] }
if ($dotEnv.ContainsKey("service_account_id")) { $ServiceAccountId = $dotEnv["service_account_id"] }
if ($dotEnv.ContainsKey("openweathermap_appid")) { $OpenWeatherMapAppId = $dotEnv["openweathermap_appid"] }

if (-not $FolderId) { throw "FolderId is required. Put folder_id into .env or pass -FolderId." }
if (-not $ServiceAccountId) { throw "ServiceAccountId is required. Pass -ServiceAccountId or set service_account_id." }
if (-not $OpenWeatherMapAppId) { throw "OpenWeatherMapAppId is required. Put openweathermap_appid into .env or pass -OpenWeatherMapAppId." }

Push-Location $PSScriptRoot

try {
    $zipPath = Join-Path $PSScriptRoot "weather_func.zip"
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    Compress-Archive -Path "index.py", "requirements.txt" -DestinationPath $zipPath

    yc serverless function create --name $FunctionName --folder-id $FolderId 2>$null

    yc serverless function version create `
        --function-name $FunctionName `
        --folder-id $FolderId `
        --runtime python312 `
        --entrypoint index.handler `
        --memory 128m `
        --execution-timeout 30s `
        --service-account-id $ServiceAccountId `
        --environment "openweathermap_appid=$OpenWeatherMapAppId" `
        --source-path $zipPath

    $function = yc serverless function get --name $FunctionName --folder-id $FolderId --format json | ConvertFrom-Json
    $schema = '{"type":"object","properties":{"city":{"type":"string","description":"City name in English, for example Moscow"}},"required":["city"]}'

    $body = @{
        folderId = $FolderId
        name = $GatewayName
        description = "Simple MCP gateway for OpenWeatherMap demo"
        serviceAccountId = $ServiceAccountId
        public = $true
        tools = @(
            @{
                name = "get_weather"
                description = "Get current weather for a city from OpenWeatherMap"
                inputJsonSchema = $schema
                action = @{
                    functionCall = @{
                        functionId = $function.id
                        tag = '$latest'
                    }
                }
            }
        )
    } | ConvertTo-Json -Depth 20

    $bodyPath = Join-Path $PSScriptRoot "mcp_gateway_body.json"
    Set-Content -Path $bodyPath -Value $body -Encoding UTF8

    $iamToken = yc iam create-token
    $operation = Invoke-RestMethod `
        -Method Post `
        -Uri "https://serverless-mcp-gateway.api.cloud.yandex.net/mcpgateway/v1/mcpGateways" `
        -Headers @{ Authorization = "Bearer $iamToken" } `
        -ContentType "application/json" `
        -InFile $bodyPath

    $gatewayId = $operation.metadata.mcpGatewayId
    Write-Host "MCP Gateway ID: $gatewayId"
    Write-Host "Wait until the gateway becomes ACTIVE, then run:"
    Write-Host "yc serverless mcp-gateway get --id $gatewayId --format json"
    Write-Host "Use baseDomain + /sse as MCP URL in the notebook."
}
finally {
    Pop-Location
}
