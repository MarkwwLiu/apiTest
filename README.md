# API Test Framework

自動化 API 測試框架，支援 **HTTP REST API** 與 **WebSocket (WSS)** 測試。
只需提供 API 定義 (YAML/JSON)，即可自動產生 pytest 測試案例並執行。

## Architecture / 架構圖

```
 ┌───────────────────────────────────────────────────────────────┐
 │                    使用者提供 API 定義                          │
 │              api_definitions/*.yaml (或 .json)                │
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
 │  • 讀取 YAML / JSON API 定義檔                                │
 │  • 解析 HTTP endpoints (GET/POST/PUT/PATCH/DELETE)            │
 │  • 解析 WSS endpoints (connect / send / receive)              │
 │  • 解析 Scenarios (多 API 串接)                                │
 └──────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
 ┌───────────────────────────────────────────────────────────────┐
 │                 Auto Test Case Generator                      │
 │           api_test/generators/pytest_generator.py              │
 │                                                               │
 │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
 │  │  HTTP Tests    │  │  WSS Tests     │  │ Scenario Tests │  │
 │  │  (requests)    │  │ (websocket)    │  │ (多 API 驗證)  │  │
 │  └────────────────┘  └────────────────┘  └────────────────┘  │
 │                                                               │
 │  → 自動產生 pytest 測試檔 → generated_tests/                   │
 └─────────┬──────────────────┬──────────────────┬───────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
 ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │  Test Data   │    │    pytest    │    │   Reports    │
 │  (解耦合)    │    │    Engine    │    │  (HTML/終端)  │
 │  test_data/  │    │              │    │  reports/    │
 └──────────────┘    └──────────────┘    └──────────────┘
```

## Flow / 執行流程

```
 1. 放置 API 定義 YAML 到 api_definitions/
 2. (可選) 放置測試資料到 test_data/
                │
                ▼
 3. python run_tests.py
                │
                ├──→ 解析 api_definitions/ 下所有 YAML
                ├──→ 自動產生 pytest 測試檔到 generated_tests/
                └──→ 執行 pytest 並輸出結果
                        │
                        ▼
 4. 查看結果:
    • 終端直接顯示 pass / fail
    • reports/report.html  (加 --html 旗標)
```

## Directory Structure / 目錄結構

```
apiTest/
├── api_definitions/              # API 定義檔 ← 使用者在此新增
│   ├── example_http.yaml             # HTTP REST API 範例
│   ├── example_wss.yaml              # WebSocket API 範例
│   └── example_scenario.yaml         # 多 API 串接範例
│
├── test_data/                    # 測試資料 (與定義完全解耦合) ← 使用者在此新增
│   └── example_posts.yaml
│
├── api_test/                     # 框架核心
│   ├── core/
│   │   ├── api_parser.py             # API 定義解析器
│   │   └── test_data_loader.py       # 測試資料載入器
│   ├── executors/
│   │   ├── http_executor.py          # HTTP 測試執行器 (requests)
│   │   └── wss_executor.py           # WebSocket 測試執行器
│   └── generators/
│       └── pytest_generator.py       # pytest 測試案例自動產生器
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

# 6. Verbose 輸出
python run_tests.py -v

# 7. 只跑符合關鍵字的測試
python run_tests.py -k "list_posts"
```

## API Definition Format / API 定義格式

### HTTP API

```yaml
name: "My API"
base_url: "https://api.example.com"

default_headers:
  Content-Type: "application/json"
  Authorization: "Bearer YOUR_TOKEN"

test_data_file: "my_data.yaml"    # 引用 test_data/ 下的資料

http_endpoints:
  - name: "get_users"
    url: "/api/v1/users"
    method: "GET"
    expected_status: 200
    expected_body:              # 驗證回傳 JSON 部分欄位
      success: true
    timeout: 10

  - name: "create_user"
    url: "/api/v1/users"
    method: "POST"
    expected_status: 201
    body:
      name: "test"
      email: "test@example.com"
```

### WebSocket API

```yaml
name: "My WSS"
base_url: "wss://ws.example.com"

wss_endpoints:
  - name: "echo_test"
    url: "wss://ws.example.com/socket"
    timeout: 10
    messages:
      - action: "send"             # 純文字發送
        data: "hello"
      - action: "receive"          # 接收並驗證
        expected: "hello"
      - action: "send_json"        # JSON 發送
        data: { "type": "ping" }
      - action: "receive_json"     # 接收 JSON 並驗證部分欄位
        expected: { "type": "pong" }
```

### Scenario (多 API 串接)

```yaml
name: "User Flow"
base_url: "https://api.example.com"

http_endpoints:
  - name: "login"
    url: "/auth/login"
    method: "POST"
    expected_status: 200
    body: { "username": "test", "password": "pass" }

  - name: "get_profile"
    url: "/users/me"
    method: "GET"
    expected_status: 200

scenarios:
  - name: "login_then_profile"
    steps:
      - name: "Login"
        endpoint_ref: "login"           # 引用上面定義的 endpoint
        save:                           # 從回應中擷取值
          token: "data.access_token"
      - name: "Get Profile"
        endpoint_ref: "get_profile"
```

## Test Data Format / 測試資料格式

放在 `test_data/` 下，與 API 定義完全解耦合：

```yaml
data:
  - name: "case_1"
    userId: 1
    title: "Test A"
  - name: "case_2"
    userId: 2
    title: "Test B"
```

當 endpoint 有 `body` 且定義了 `test_data_file` 時，
框架會用 `@pytest.mark.parametrize` 自動對每筆資料產生獨立測試。

## Adding New Tests / 新增測試

只需兩步驟：

1. 在 `api_definitions/` 新增一個 YAML 描述你的 API
2. (可選) 在 `test_data/` 新增測試資料

執行 `python run_tests.py`，測試案例自動產生並執行。
