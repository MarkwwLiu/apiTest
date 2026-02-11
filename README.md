# API Stress Test Framework

自動化 API 壓力測試框架，只需提供 API 定義 (YAML/JSON)，即可自動產生壓力測試案例並執行。

## Architecture / 架構圖

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │                        使用者提供 API 定義                            │
 │                  api_definitions/*.yaml (或 .json)                   │
 │                                                                      │
 │  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
 │  │ single_api.yaml  │  │ multi_api.yaml   │  │ scenario.yaml      │ │
 │  │ (單一 API)        │  │ (多個 API)        │  │ (API 串接情境)      │ │
 │  └──────────────────┘  └──────────────────┘  └────────────────────┘ │
 └─────────────────────────────┬────────────────────────────────────────┘
                               │
                               ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │                      API Definition Parser                           │
 │               stress_test/core/api_parser.py                         │
 │                                                                      │
 │  • 讀取 YAML / JSON API 定義檔                                       │
 │  • 解析端點 URL、HTTP Method、Headers、Body、Query Params             │
 │  • 產生 StressTestConfig 資料結構                                     │
 └─────────────────────────────┬────────────────────────────────────────┘
                               │
                               ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │                  Auto Test Case Generator                            │
 │            stress_test/generators/locust_generator.py                 │
 │                                                                      │
 │  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐          │
 │  │ Single Mode  │  │  Multi Mode   │  │  Scenario Mode   │          │
 │  │ 單一端點壓測  │  │ 多端點加權壓測 │  │ API 串接流程壓測  │          │
 │  └──────────────┘  └───────────────┘  └──────────────────┘          │
 │                                                                      │
 │  → 自動產生 Locust Python 測試檔 → generated_tests/                   │
 └────────┬───────────────────┬────────────────────┬────────────────────┘
          │                   │                    │
          ▼                   ▼                    ▼
 ┌────────────────┐  ┌────────────────┐   ┌────────────────────┐
 │   Test Data    │  │  Stress Test   │   │  Report Generator  │
 │   (解耦合)     │  │    Engine      │   │                    │
 │                │  │                │   │  • HTML Report      │
 │  test_data/    │  │  Locust 引擎   │   │  • CSV Stats        │
 │  *.yaml/json   │  │  (headless or  │   │  • JSON Summary     │
 │  *.csv         │  │   web UI)      │   │                    │
 └────────────────┘  └────────────────┘   └────────────────────┘
```

## Flow / 執行流程

```
 1. 放置 API 定義 YAML 到 api_definitions/
 2. (可選) 放置測試資料到 test_data/
                │
                ▼
 3. python run_stress_test.py
                │
                ├──→ 解析 api_definitions/ 下所有 YAML
                ├──→ 自動產生 Locust 測試檔到 generated_tests/
                ├──→ 執行壓力測試 (Locust headless)
                └──→ 產生報表到 reports/
                        │
                        ▼
 4. 查看結果:
    • reports/*_stats.csv     ← 詳細數據
    • reports/*.html          ← 視覺化報告
    • reports/*_summary.json  ← 摘要結果
```

## Directory Structure / 目錄結構

```
apiTest/
├── api_definitions/          # API 定義檔 (YAML/JSON) ← 使用者在此新增
│   ├── example_single_api.yaml
│   ├── example_multi_api.yaml
│   └── example_scenario_chain.yaml
│
├── test_data/                # 測試資料 (與 API 定義解耦合) ← 使用者在此新增
│   └── example_users.yaml
│
├── stress_test/              # 框架核心程式碼
│   ├── core/
│   │   ├── api_parser.py         # API 定義解析器
│   │   ├── test_data_loader.py   # 測試資料載入器
│   │   └── engine.py             # 壓力測試引擎 (Locust wrapper)
│   ├── generators/
│   │   └── locust_generator.py   # 自動測試案例產生器
│   └── reports/
│       └── report_generator.py   # 報表產生器
│
├── generated_tests/          # 自動產生的 Locust 測試檔 (git ignored)
├── reports/                  # 測試報告輸出 (git ignored)
├── run_stress_test.py        # 主程式入口 (CLI)
└── requirements.txt          # Python 套件依賴
```

## Quick Start / 快速開始

```bash
# 1. 安裝套件
pip install -r requirements.txt

# 2. 執行範例壓力測試 (使用 example API definitions)
python run_stress_test.py

# 3. 只產生測試檔不執行
python run_stress_test.py --generate-only

# 4. 指定單一 API 定義檔
python run_stress_test.py --api-file api_definitions/example_single_api.yaml

# 5. 指定模式 (single / multi / scenario / all)
python run_stress_test.py --mode scenario

# 6. 自訂壓測參數
python run_stress_test.py --users 50 --spawn-rate 10 --run-time 2m

# 7. 啟動 Locust Web UI (可視化操作)
python run_stress_test.py --web-ui
```

## API Definition Format / API 定義格式

在 `api_definitions/` 下新增 YAML 檔，格式如下：

```yaml
name: "My API Test"
base_url: "https://api.example.com"

default_headers:
  Content-Type: "application/json"
  Authorization: "Bearer YOUR_TOKEN"

# 引用 test_data/ 下的測試資料 (解耦合)
test_data_file: "my_test_data.yaml"

stress_config:
  users: 20          # 併發使用者數
  spawn_rate: 5      # 每秒產生使用者速率
  run_time: "1m"     # 測試持續時間

endpoints:
  - name: "get_items"
    url: "/api/v1/items"
    method: "GET"
    expected_status: 200
    timeout: 10
    weight: 5          # 權重 (multi mode 使用)
    tags: ["read"]

  - name: "create_item"
    url: "/api/v1/items"
    method: "POST"
    expected_status: 201
    timeout: 15
    weight: 2
    body:
      name: "test item"
      value: 100
    tags: ["write"]
```

## Test Data Format / 測試資料格式

在 `test_data/` 下新增資料檔 (YAML/JSON/CSV)，與 API 定義完全解耦合：

```yaml
# test_data/my_test_data.yaml
data:
  - userId: 1
    name: "User A"
    email: "a@test.com"
  - userId: 2
    name: "User B"
    email: "b@test.com"
```

測試產生器會自動將資料中符合的 key 合併到 request body 中。

## Test Modes / 測試模式

| Mode       | Description                          | Use Case                    |
|------------|--------------------------------------|-----------------------------|
| `single`   | 對第一個端點做壓力測試                 | 單一 API 效能基準測試         |
| `multi`    | 對所有端點以 weight 權重做壓力測試     | 模擬真實混合流量              |
| `scenario` | 按順序串接執行所有端點                 | 模擬使用者操作流程            |
| `all`      | 同時產生上述三種測試                   | 完整測試覆蓋                 |

## Adding New Tests / 新增測試

只需兩步驟：

1. 在 `api_definitions/` 新增一個 YAML 檔描述你的 API
2. (可選) 在 `test_data/` 新增對應的測試資料

然後執行 `python run_stress_test.py`，框架會自動產生並執行壓力測試。
