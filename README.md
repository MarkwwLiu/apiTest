# API Test Framework

自動化 API 功能測試框架，支援 **HTTP REST API** 與 **WebSocket (WSS)** 測試。
只需提供 API 定義 (YAML/JSON)，即可自動產生 pytest 測試案例並執行。

## Features / 功能特色

| 分類 | 功能 | 說明 |
|------|------|------|
| **協定** | HTTP + WebSocket | 同時支援 REST API 與 WSS 端點測試 |
| **環境變數** | `${VAR:-default}` | 切換 dev / staging / prod 環境 |
| **認證** | Bearer / API Key / Login | 三種認證模式，Login 可自動取得 token |
| **Retry** | 全域或單一 endpoint | 含 backoff 策略、狀態碼過濾、timeout 重試 |
| **Response 驗證** | 進階比對 | regex、type check、array length、exists、巢狀 dict |
| **回應時間** | `max_response_time` | 限制 API 回應時間（毫秒） |
| **Scenario** | 多 API 串接 | 支援 setup / teardown、變數傳遞、override |
| **Tags 過濾** | `--tags` / `--skip-tags` | 依標籤選擇性執行測試 |
| **Debug** | `--debug` | 完整 request / response 日誌輸出 |
| **報告** | JSON + HTML | 自動產生 `reports/report.json`，可加 `--html` |
| **檔案上傳** | multipart/form-data | 支援 `upload_files` 欄位 |
| **WSS 進階** | binary / ping / wait | 二進位訊息、心跳、延遲動作 |
| **資料解耦合** | `test_data/` | 測試資料與 API 定義完全分離 |
| **獨立匯出** | `--export` | 匯出拋棄式單檔腳本，不需安裝框架即可執行 |

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
                            │
                            ▼
                  ┌──────────────────┐
                  │ Standalone Export │
                  │ (拋棄式單檔腳本) │
                  │  exports/*.py    │
                  └──────────────────┘
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
│   ├── exporters/
│   │   └── standalone_exporter.py    # 匯出獨立可執行腳本
│   └── generators/
│       └── pytest_generator.py       # pytest 自動產生器 (含 conftest / JSON report)
│
├── generated_tests/              # 自動產生的 pytest 檔 (git ignored)
├── exports/                      # 匯出的獨立腳本 (git ignored)
├── reports/                      # 測試報告 (git ignored)
├── run_tests.py                  # 主程式入口 (CLI)
└── requirements.txt
```

## Quick Start / 快速開始

```bash
# 1. 安裝套件
pip install -r requirements.txt

# 2. 執行所有 API 測試（自動產生 + 執行）
python run_tests.py

# 3. 只產生測試檔不執行
python run_tests.py --generate-only

# 4. 測試單一 API 定義
python run_tests.py --api-file api_definitions/example_http.yaml

# 5. 帶 HTML 報告
python run_tests.py --html

# 6. Verbose + Debug（看完整 request/response）
python run_tests.py -v --debug

# 7. 只跑符合關鍵字的測試
python run_tests.py -k "list_posts"

# 8. 只跑特定 tag 的測試
python run_tests.py --tags read

# 9. 跳過特定 tag 的測試
python run_tests.py --skip-tags write

# 10. 組合 tag 過濾
python run_tests.py --tags read posts --skip-tags comments

# 11. 用環境變數切換目標 API
API_BASE_URL=https://staging.api.com API_TOKEN=xxx python run_tests.py

# 12. 匯出獨立腳本（拋棄式腳本）
python run_tests.py --export generated_tests/test_example_http_api_http.py

# 13. 指定匯出路徑
python run_tests.py --export generated_tests/test_example_http_api_http.py --output /tmp/my_test.py
```

## CLI Reference / 命令列參數

| 參數 | 說明 | 範例 |
|------|------|------|
| `--api-dir DIR` | API 定義檔目錄（預設 `api_definitions/`） | `--api-dir my_apis/` |
| `--api-file FILE` | 測試單一 API 定義檔 | `--api-file api_definitions/example_http.yaml` |
| `--output-dir DIR` | 產生的測試檔目錄（預設 `generated_tests/`） | `--output-dir tests/` |
| `--generate-only` | 只產生測試檔，不執行 | `--generate-only` |
| `--html` | 產生 HTML 報告（`reports/report.html`） | `--html` |
| `-v, --verbose` | Verbose pytest 輸出 | `-v` |
| `-k EXPR` | 只執行符合關鍵字的測試 | `-k "list_posts"` |
| `--tags TAG [TAG ...]` | 只執行含指定 tag 的測試 | `--tags read posts` |
| `--skip-tags TAG [TAG ...]` | 跳過含指定 tag 的測試 | `--skip-tags write` |
| `--debug` | 開啟 debug logging（等同 `API_TEST_LOG_LEVEL=DEBUG`） | `--debug` |
| `--export FILE` | 匯出測試檔為獨立腳本 | `--export generated_tests/test_xxx.py` |
| `--output PATH` | 搭配 `--export` 指定輸出路徑 | `--output /tmp/my_test.py` |

## Standalone Export / 匯出獨立腳本

將自動產生的測試檔匯出為**獨立可執行的單一 Python 檔案**。
所有依賴（HttpExecutor、WssExecutor、測試資料、日誌設定、JSON 報告）全部內嵌在同一個檔案中，
不需要安裝框架，只需要安裝基本套件即可執行。

### 使用流程

```bash
# Step 1: 先產生測試檔
python run_tests.py --generate-only

# Step 2: 匯出指定的測試檔為獨立腳本
python run_tests.py --export generated_tests/test_example_http_api_http.py
# → exports/test_example_http_api_http_standalone.py

# Step 3: 在任意機器上執行（只需 pip 安裝基本套件）
pip install pytest requests websocket-client
pytest exports/test_example_http_api_http_standalone.py -v

# 搭配 debug 模式
API_TEST_LOG_LEVEL=DEBUG pytest exports/test_example_http_api_http_standalone.py -v
```

### 匯出內容

匯出器會自動分析測試檔的依賴，將以下內容內嵌到單一 `.py` 檔：

| 內容 | 說明 |
|------|------|
| Executor 原始碼 | 根據測試類型自動嵌入 HttpExecutor 和/或 WssExecutor |
| 測試資料 | YAML/JSON 測試資料轉為 Python literal 直接內嵌 |
| Logging 設定 | 支援 `API_TEST_LOG_LEVEL` 環境變數 |
| JSON 報告 hook | 執行後自動產生 `reports/report.json` |
| 測試案例 | 移除框架 import，保留所有測試函式 |

### 適用場景

- 將測試腳本交給其他團隊，對方不需安裝完整框架
- CI/CD pipeline 中只需部署單一檔案
- 快速分享給同事進行一次性測試
- 離線環境下執行（預先安裝 pip 套件即可）

### 支援匯出的測試類型

```bash
# HTTP 測試
python run_tests.py --export generated_tests/test_example_http_api_http.py

# WebSocket 測試
python run_tests.py --export generated_tests/test_example_websocket_api_wss.py

# Scenario 串接測試
python run_tests.py --export generated_tests/test_example_scenario_scenario.py

# 指定自訂輸出路徑
python run_tests.py --export generated_tests/test_example_http_api_http.py --output /tmp/quick_test.py
```

## API Definition Format / API 定義格式

### HTTP API（完整範例）

```yaml
name: "My API"
base_url: "${API_BASE_URL:-https://api.example.com}"

default_headers:
  Content-Type: "application/json"

# ── Authentication（三選一）──
auth:
  # 方式 1: Bearer Token
  type: "bearer"
  token: "${API_TOKEN}"

  # 方式 2: API Key
  # type: "api_key"
  # api_key_header: "X-API-Key"
  # api_key_value: "${API_KEY}"

  # 方式 3: Login Flow（自動登入取 token）
  # type: "login"
  # login_url: "/auth/login"
  # login_method: "POST"
  # login_body: { "username": "test", "password": "pass" }
  # token_json_path: "data.access_token"

# ── 全域 Retry ──
retry:
  max_retries: 2
  backoff: [1, 2, 4]             # 每次重試的等待秒數
  retry_on_status: [500, 502, 503]
  retry_on_timeout: true

# 引用 test_data/ 下的測試資料（解耦合）
test_data_file: "my_data.yaml"

http_endpoints:
  - name: "get_users"
    url: "/api/v1/users"
    method: "GET"
    expected_status: 200
    max_response_time: 3000        # 回應時間不超過 3 秒
    expected_body:
      success: true
      data: "type:array"           # 型別檢查
      total: "type:integer"
    expected_headers:
      content-type: "regex:application/json"
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
    # 可覆蓋全域 retry
    retry:
      max_retries: 3
      backoff: [1, 2, 4, 8]

  - name: "upload_avatar"
    url: "/api/v1/users/1/avatar"
    method: "POST"
    content_type: "multipart/form-data"
    upload_files:
      avatar: "test_data/avatar.png"
    expected_status: 200
    allow_redirects: false
    tags: ["write", "upload"]
```

### HTTP Endpoint 完整欄位

| 欄位 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| `name` | string | Y | - | 端點名稱（會轉為測試函式名） |
| `url` | string | Y | - | API 路徑（會接在 `base_url` 後面） |
| `method` | string | N | `GET` | HTTP 方法 |
| `headers` | dict | N | `{}` | 額外 Headers（會合併 `default_headers`） |
| `query_params` | dict | N | `{}` | Query string 參數 |
| `body` | any | N | `null` | Request body |
| `content_type` | string | N | `application/json` | Content-Type |
| `expected_status` | int | N | `200` | 期望的 HTTP 狀態碼 |
| `expected_body` | dict | N | `null` | Response body 驗證規則 |
| `expected_headers` | dict | N | `null` | Response header 驗證（大小寫不敏感） |
| `max_response_time` | int | N | `null` | 最大回應時間（毫秒） |
| `timeout` | int | N | `30` | 請求 timeout（秒） |
| `tags` | list | N | `[]` | 測試標籤（對應 pytest markers） |
| `retry` | dict | N | 全域設定 | 重試設定（覆蓋全域） |
| `upload_files` | dict | N | `null` | 檔案上傳 `{"欄位名": "檔案路徑"}` |
| `allow_redirects` | bool | N | `true` | 是否跟隨 HTTP 重導向 |

### 進階 Response 驗證語法

```yaml
expected_body:
  # 精確比對
  id: 1
  name: "John"

  # 正規表達式
  email: "regex:^[\\w.]+@[\\w.]+$"

  # 型別檢查（支援: string, int, float, number, bool, list, dict, null）
  age: "type:integer"
  tags: "type:array"

  # 陣列長度（支援: >N, >=N, <N, 或精確值）
  items: "len:>0"
  results: "len:10"

  # 欄位存在檢查（只檢查 key 存在，不管值）
  avatar_url: "exists:true"
  deleted_at: "exists:false"

  # 巢狀物件（遞迴比對）
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
    tags: ["wss", "echo"]
    messages:
      - action: "send"             # 純文字發送
        data: "hello"
      - action: "receive"          # 接收並驗證
        timeout: 5
        expected: "hello"
      - action: "send_json"        # JSON 發送
        data: { "type": "ping" }
      - action: "receive_json"     # 接收 JSON 並驗證部分欄位
        timeout: 5
        expected: { "type": "pong" }
      - action: "send_binary"      # 二進位發送
        data: "binary content"
      - action: "ping"             # WebSocket ping
        data: "keepalive"
      - action: "pong"             # WebSocket pong
        data: "response"
      - action: "wait"             # 等待 N 秒
        timeout: 2
```

### WSS Message Action 完整列表

| Action | 說明 | `data` 用途 | `expected` 用途 |
|--------|------|-------------|-----------------|
| `send` | 發送純文字 | 發送內容 | - |
| `send_json` | 發送 JSON | dict/list 物件 | - |
| `send_binary` | 發送二進位 | string 或 byte list | - |
| `receive` | 接收純文字 | - | 期望收到的文字 |
| `receive_json` | 接收 JSON | - | 部分欄位比對 |
| `ping` | 發送 WebSocket ping | ping payload | - |
| `pong` | 發送 WebSocket pong | pong payload | - |
| `wait` | 等待指定秒數 | - | -（使用 `timeout` 欄位） |

### Scenario（含 Setup / Teardown）

```yaml
scenarios:
  - name: "user_flow"
    tags: ["scenario", "e2e"]

    # 測試前執行（可選）
    setup:
      - name: "Create test user"
        endpoint_ref: "create_user"
        save:
          user_id: "data.id"         # 儲存回應中的值到 context

    # 測試步驟
    steps:
      - name: "Login"
        endpoint_ref: "login"
        save:
          token: "data.access_token"
      - name: "Get Profile"
        endpoint_ref: "get_profile"
        override_headers:
          Authorization: "Bearer {token}"  # 使用 context 中的變數
      - name: "Update Profile"
        endpoint_ref: "update_user"
        override_body:                     # 覆蓋 endpoint 定義的 body
          name: "New Name"
        override_params:                   # 覆蓋 query params
          include: "details"

    # 測試後執行（無論成敗都會跑，可選）
    teardown:
      - name: "Delete test user"
        endpoint_ref: "delete_user"
```

### Scenario Step 完整欄位

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `name` | string | Y | 步驟名稱 |
| `endpoint_ref` | string | Y | 引用的 endpoint name |
| `save` | dict | N | 從 response 儲存變數 `{"var_name": "json.path"}` |
| `override_body` | dict | N | 覆蓋 endpoint 定義的 body |
| `override_params` | dict | N | 覆蓋 endpoint 定義的 query params |
| `override_headers` | dict | N | 追加 / 覆蓋 headers |

## Test Data / 測試資料

測試資料放在 `test_data/` 目錄，與 API 定義完全解耦合。支援 YAML、JSON、CSV 格式。

### YAML 格式

```yaml
# test_data/users.yaml
data:
  - name: "user_1"
    userId: 1
    title: "First Post"
    body: "Content from user 1"

  - name: "user_2"
    userId: 2
    title: "Second Post"
    body: "Content from user 2"
```

### JSON 格式

```json
{
  "data": [
    {"name": "user_1", "userId": 1, "title": "Post A"},
    {"name": "user_2", "userId": 2, "title": "Post B"}
  ]
}
```

### CSV 格式

```csv
name,userId,title,body
user_1,1,Post A,Content A
user_2,2,Post B,Content B
```

### 使用方式

在 API 定義中透過 `test_data_file` 引用：

```yaml
test_data_file: "users.yaml"
```

框架會自動將測試資料與 `body` 中同名的欄位合併，並使用 `@pytest.mark.parametrize` 產生多組測試。

## Environment Variables / 環境變數

在 YAML 中使用 `${VAR_NAME}` 語法，框架會在解析時自動替換：

```yaml
base_url: "${API_BASE_URL:-https://localhost:3000}"  # 有預設值
auth:
  token: "${API_TOKEN}"                               # 無預設值（必須設定）
```

使用方式：

```bash
# Linux/Mac
export API_BASE_URL=https://staging.api.com
export API_TOKEN=my-secret-token
python run_tests.py

# 或一行式
API_BASE_URL=https://staging.api.com API_TOKEN=xxx python run_tests.py
```

### 框架內建環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `API_TEST_LOG_LEVEL` | `WARNING` | 日誌等級（`DEBUG` / `INFO` / `WARNING` / `ERROR`） |

## Authentication / 認證

### Bearer Token

```yaml
auth:
  type: "bearer"
  token: "${API_TOKEN}"
```

### API Key

```yaml
auth:
  type: "api_key"
  api_key_header: "X-API-Key"       # Header 名稱（預設 X-API-Key）
  api_key_value: "${API_KEY}"
```

### Login Flow（自動登入）

```yaml
auth:
  type: "login"
  login_url: "/auth/login"
  login_method: "POST"
  login_body:
    username: "${TEST_USER:-testuser}"
    password: "${TEST_PASS:-testpass}"
  token_json_path: "data.access_token"  # 從回應中擷取 token 的 JSON 路徑
```

Login Flow 執行順序：
1. 向 `login_url` 發送請求
2. 從回應 JSON 中依 `token_json_path` 擷取 token
3. 自動設定 `Authorization: Bearer <token>` 到後續所有請求

## Retry / 重試機制

### 全域設定

```yaml
retry:
  max_retries: 3
  backoff: [1, 2, 4]               # 第 1/2/3 次重試分別等待 1/2/4 秒
  retry_on_status: [500, 502, 503, 504]
  retry_on_timeout: true
```

### 單一 Endpoint 覆蓋

```yaml
http_endpoints:
  - name: "slow_api"
    retry:
      max_retries: 5
      backoff: [2, 4, 8, 16, 32]
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
14:30:01 [api_test.http] DEBUG:   Request headers: {'Content-Type': 'application/json', ...}
14:30:01 [api_test.http] DEBUG:   Request body: {"name": "test"}
14:30:01 [api_test.http] DEBUG:   Response body: {"data": [...]}
```

WSS 測試也有同樣的日誌：

```
14:30:02 [api_test.wss] DEBUG: [echo_test] Connected to wss://ws.example.com
14:30:02 [api_test.wss] DEBUG:   -> send: hello
14:30:02 [api_test.wss] DEBUG:   <- receive: hello
```

## Reports / 測試報告

### JSON 報告（自動產生）

每次執行自動產生 `reports/report.json`：

```json
{
  "timestamp": "2026-02-12T14:30:00",
  "total": 15,
  "passed": 13,
  "failed": 2,
  "skipped": 0,
  "results": [
    {
      "test": "test_list_posts",
      "outcome": "passed",
      "duration": 0.123,
      "tags": ["read", "posts"]
    }
  ]
}
```

### HTML 報告

加 `--html` 旗標可額外產生 HTML 報告：

```bash
python run_tests.py --html
# → reports/report.html
```

## Adding New Tests / 新增測試

只需兩步驟：

1. 在 `api_definitions/` 新增一個 YAML 描述你的 API
2. （可選）在 `test_data/` 新增測試資料

執行 `python run_tests.py`，測試案例自動產生並執行。

### 範例：新增一個 API 測試

```yaml
# api_definitions/my_service.yaml
name: "My Service API"
base_url: "https://api.myservice.com"

default_headers:
  Authorization: "Bearer ${MY_TOKEN}"

http_endpoints:
  - name: "health_check"
    url: "/health"
    method: "GET"
    expected_status: 200
    expected_body:
      status: "ok"
    tags: ["health"]

  - name: "get_items"
    url: "/api/items"
    method: "GET"
    expected_status: 200
    expected_body:
      data: "type:array"
      total: "type:integer"
    max_response_time: 2000
    tags: ["read", "items"]
```

```bash
python run_tests.py --api-file api_definitions/my_service.yaml -v
```

## Requirements / 套件需求

```
pytest>=8.0.0
requests>=2.31.0
websocket-client>=1.7.0
pyyaml>=6.0
jinja2>=3.1.0
pytest-html>=4.1.0
```

安裝：`pip install -r requirements.txt`

獨立匯出的腳本只需：`pip install pytest requests websocket-client`
