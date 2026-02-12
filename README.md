# API Test Framework

自動化 API 測試框架，支援 **HTTP REST API** 與 **WebSocket (WSS)** 測試。
只需提供 API 定義 (YAML/JSON)，即可自動產生 pytest 測試案例並執行。

## Features / 功能特色

- **HTTP + WebSocket** — 同時支援 REST API 與 WSS 端點測試
- **環境變數替換** — `${VAR}` / `${VAR:-default}` 語法，切換 dev/staging/prod
- **Authentication** — Bearer Token / API Key / Login Flow 三種模式
- **Retry 機制** — 可全域或單一 endpoint 設定，含 backoff 與狀態碼過濾
- **進階 Response 驗證** — 巢狀 dict、regex、type check、array length、exists check
- **Response Time 斷言** — `max_response_time` 限制回應時間
- **Setup / Teardown** — Scenario 支援前置/後置動作，teardown 無論成敗都執行
- **Tags 過濾** — `--tags read` / `--skip-tags write` 依標籤執行
- **Debug Logging** — `--debug` 或 `API_TEST_LOG_LEVEL=DEBUG` 看完整 request/response
- **JSON 報告** — 每次執行自動產生 `reports/report.json`
- **File Upload** — 支援 `multipart/form-data` 檔案上傳
- **WSS 進階** — 支援 binary message、ping/pong、wait 動作
- **測試資料解耦合** — `test_data/` 與 API 定義完全分離

## Architecture / 架構圖

```
 ┌───────────────────────────────────────────────────────────────┐
 │                    使用者提供 API 定義                          │
 │              api_definitions/*.yaml (或 .json)                │
 │                                                               │
 │  支援: ${ENV_VAR} 環境變數、auth、retry、tags                  │
 │                                                               │
 │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
 │  │  HTTP APIs     │  │  WSS APIs      │  │  Scenario      │  │
 │  │  (REST 端點)   │  │  (WebSocket)   │  │  (串接流程)    │  │
 │  └────────────────┘  └────────────────┘  └────────────────┘  │
 └──────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
 ┌───────────────────────────────────────────────────────────────┐
 │                    API Definition Parser                       │
 │              api_test/core/api_parser.py                       │
 │                                                               │
 │  • ${ENV_VAR:-default} 環境變數替換                            │
 │  • 解析 HTTP / WSS endpoints                                  │
 │  • 解析 auth (bearer / api_key / login)                       │
 │  • 解析 retry (backoff / status code / timeout)               │
 │  • 解析 scenarios (steps + setup + teardown)                  │
 └──────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
 ┌───────────────────────────────────────────────────────────────┐
 │                 Auto Test Case Generator                      │
 │           api_test/generators/pytest_generator.py              │
 │                                                               │
 │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
 │  │  HTTP Tests    │  │  WSS Tests     │  │ Scenario Tests │  │
 │  │  + retry       │  │  + retry       │  │ + setup        │  │
 │  │  + auth        │  │  + binary/ping │  │ + teardown     │  │
 │  │  + upload      │  │  + wait        │  │ + override     │  │
 │  └────────────────┘  └────────────────┘  └────────────────┘  │
 │                                                               │
 │  + conftest.py (logging + JSON report)                        │
 │  → 自動產生 pytest 測試檔 → generated_tests/                   │
 └─────────┬──────────────────┬──────────────────┬───────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
 ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │  Test Data   │    │    pytest    │    │   Reports    │
 │  (解耦合)    │    │    Engine    │    │  JSON + HTML │
 │  test_data/  │    │              │    │  reports/    │
 └──────────────┘    └──────────────┘    └──────────────┘
```

## Directory Structure / 目錄結構

```
apiTest/
├── api_definitions/              # API 定義檔 ← 使用者在此新增
│   ├── example_http.yaml             # HTTP REST API 範例
│   ├── example_wss.yaml              # WebSocket API 範例
│   └── example_scenario.yaml         # 多 API 串接範例 (含 teardown)
│
├── test_data/                    # 測試資料 (與定義完全解耦合) ← 使用者在此新增
│   └── example_posts.yaml
│
├── api_test/                     # 框架核心
│   ├── core/
│   │   ├── api_parser.py             # API 定義解析器 (含 env var / auth / retry)
│   │   └── test_data_loader.py       # 測試資料載入器
│   ├── executors/
│   │   ├── http_executor.py          # HTTP 執行器 (retry / auth / upload / 進階驗證)
│   │   └── wss_executor.py           # WSS 執行器 (retry / binary / ping / wait)
│   └── generators/
│       └── pytest_generator.py       # pytest 自動產生器 (含 conftest / JSON report)
│
├── generated_tests/              # 自動產生的 pytest 檔 (git ignored)
├── reports/                      # 測試報告 (git ignored)
├── run_tests.py                  # 主程式入口 (CLI)
└── requirements.txt
```

## Quick Start / 快速開始

```bash
# 1. 安裝套件
pip install -r requirements.txt

# 2. 執行所有 API 測試
python run_tests.py

# 3. 只產生測試檔不執行
python run_tests.py --generate-only

# 4. 測試單一 API 定義
python run_tests.py --api-file api_definitions/example_http.yaml

# 5. 帶 HTML 報告
python run_tests.py --html

# 6. Verbose + Debug (看 request/response 詳細內容)
python run_tests.py -v --debug

# 7. 只跑符合關鍵字的測試
python run_tests.py -k "list_posts"

# 8. 只跑特定 tag 的測試
python run_tests.py --tags read

# 9. 跳過特定 tag 的測試
python run_tests.py --skip-tags write

# 10. 用環境變數切換目標 API
API_BASE_URL=https://staging.api.com API_TOKEN=xxx python run_tests.py
```

## API Definition Format / API 定義格式

### HTTP API (完整範例)

```yaml
name: "My API"
base_url: "${API_BASE_URL:-https://api.example.com}"

default_headers:
  Content-Type: "application/json"

# ── Authentication (三選一) ──
auth:
  # 方式 1: Bearer Token
  type: "bearer"
  token: "${API_TOKEN}"

  # 方式 2: API Key
  # type: "api_key"
  # api_key_header: "X-API-Key"
  # api_key_value: "${API_KEY}"

  # 方式 3: Login Flow (自動登入取 token)
  # type: "login"
  # login_url: "/auth/login"
  # login_body: { "username": "test", "password": "pass" }
  # token_json_path: "data.access_token"

# ── 全域 Retry ──
retry:
  max_retries: 2
  backoff: [1, 2, 4]
  retry_on_status: [500, 502, 503]
  retry_on_timeout: true

test_data_file: "my_data.yaml"

http_endpoints:
  - name: "get_users"
    url: "/api/v1/users"
    method: "GET"
    expected_status: 200
    max_response_time: 3000        # 回應 < 3 秒
    expected_body:
      success: true
      data: "type:array"           # 型別檢查
      total: "type:integer"
    expected_headers:
      content-type: "regex:application/json"  # header regex
    timeout: 10
    tags: ["read", "users"]

  - name: "create_user"
    url: "/api/v1/users"
    method: "POST"
    expected_status: 201
    body:
      name: "test"
      email: "test@example.com"
    tags: ["write", "users"]

  - name: "upload_avatar"
    url: "/api/v1/users/1/avatar"
    method: "POST"
    content_type: "multipart/form-data"
    upload_files:
      avatar: "test_data/avatar.png"
    expected_status: 200
    tags: ["write", "upload"]
```

### 進階 Response 驗證語法

```yaml
expected_body:
  # 精確比對
  id: 1
  name: "John"

  # 正規表達式
  email: "regex:^[\\w.]+@[\\w.]+$"

  # 型別檢查
  age: "type:integer"        # string, int, float, number, bool, list, dict, null
  tags: "type:array"

  # 陣列長度
  items: "len:>0"            # >0, >=5, <100, 或精確值 len:10

  # 欄位存在檢查
  avatar_url: "exists:true"  # 只檢查 key 存在，不管值

  # 巢狀物件 (遞迴比對)
  address:
    city: "type:string"
    zip: "regex:^\\d{5}$"
```

### WebSocket API

```yaml
name: "My WSS"
base_url: "wss://ws.example.com"

wss_endpoints:
  - name: "echo_test"
    url: "wss://ws.example.com/socket"
    timeout: 10
    retry:
      max_retries: 2
      backoff: [1, 2]
    messages:
      - action: "send"             # 純文字發送
        data: "hello"
      - action: "receive"          # 接收並驗證
        expected: "hello"
      - action: "send_json"        # JSON 發送
        data: { "type": "ping" }
      - action: "receive_json"     # 接收 JSON 並驗證部分欄位
        expected: { "type": "pong" }
      - action: "send_binary"      # 二進位發送
        data: "binary content"
      - action: "ping"             # WebSocket ping
        data: "keepalive"
      - action: "wait"             # 等待 N 秒
        timeout: 2
```

### Scenario (含 Setup / Teardown)

```yaml
scenarios:
  - name: "user_flow"
    tags: ["scenario", "e2e"]

    # 測試前執行 (可選)
    setup:
      - name: "Create test user"
        endpoint_ref: "create_user"
        save:
          user_id: "data.id"

    # 測試步驟
    steps:
      - name: "Login"
        endpoint_ref: "login"
        save:
          token: "data.access_token"
      - name: "Get Profile"
        endpoint_ref: "get_profile"
        override_headers:
          Authorization: "Bearer {token}"

    # 測試後執行 (無論成敗都會跑，可選)
    teardown:
      - name: "Delete test user"
        endpoint_ref: "delete_user"
```

## Environment Variables / 環境變數

在 YAML 中使用 `${VAR_NAME}` 語法，框架會在解析時自動替換：

```yaml
base_url: "${API_BASE_URL:-https://localhost:3000}"  # 有預設值
auth:
  token: "${API_TOKEN}"                               # 無預設值 (必須設定)
```

使用方式：
```bash
# Linux/Mac
export API_BASE_URL=https://staging.api.com
export API_TOKEN=my-secret-token
python run_tests.py

# 或一行式
API_BASE_URL=https://staging.api.com python run_tests.py
```

## Debug Logging / 除錯日誌

測試失敗時，使用 `--debug` 查看完整 request/response：

```bash
python run_tests.py --debug
# 或
API_TEST_LOG_LEVEL=DEBUG python run_tests.py
```

輸出範例：
```
14:30:01 [api_test.http] DEBUG: [get_users] GET https://api.example.com/users -> 200 (123.4ms)
14:30:01 [api_test.http] DEBUG:   Request headers: {...}
14:30:01 [api_test.http] DEBUG:   Response body: {"data": [...]}
```

## Reports / 測試報告

每次執行自動產生 `reports/report.json`：

```json
{
  "timestamp": "2026-02-12T14:30:00",
  "total": 15,
  "passed": 13,
  "failed": 2,
  "skipped": 0,
  "results": [
    {"test": "test_list_posts", "outcome": "passed", "duration": 0.123, "tags": ["read", "posts"]}
  ]
}
```

加 `--html` 旗標可額外產生 HTML 報告。

## Adding New Tests / 新增測試

只需兩步驟：

1. 在 `api_definitions/` 新增一個 YAML 描述你的 API
2. (可選) 在 `test_data/` 新增測試資料

執行 `python run_tests.py`，測試案例自動產生並執行。
