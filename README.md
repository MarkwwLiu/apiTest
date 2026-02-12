# API Test Framework

自動化 API 測試框架 — 提供 YAML 定義，自動產生 pytest 測試並執行。

---

## 一、開發流程圖

```
 需求提出
    │
    ▼
 開 feature branch ──→ 規劃需求（設計方案）
    │
    ▼
 開發實作
    │
    ▼
 AI 自動跑 unit test / pytest（失敗自動 retry 3 次）
    │
    ├─ FAIL → 修正 → 重跑測試（迴圈）
    │
    ▼
 Code Review（AI 自檢）
    │
    ▼
 請使用者 Review
    │
    ├─ 不同意 → 回到「開發實作」繼續迴圈
    │
    ▼
 使用者同意 → Merge to main
```

---

## 二、架構圖

```
apiTest/
├── api_definitions/          # YAML/JSON API 定義（使用者新增）
├── test_data/                # 測試資料（與定義解耦合）
│
├── api_test/                 # 框架核心
│   ├── core/                     # 解析器 + 資料載入
│   ├── executors/                # HTTP / WSS 執行器
│   ├── exporters/                # 獨立腳本匯出
│   └── generators/               # pytest 自動產生
│
├── generated_tests/          # 自動產生的測試檔
├── exports/                  # 匯出的獨立腳本
├── reports/                  # JSON / HTML 報告
├── run_tests.py              # CLI 入口
└── requirements.txt

資料流：
  YAML 定義 → Parser → Generator → pytest → Reports
                                      ↓
                                   Exporter → 獨立單檔腳本
```

**支援功能一覽：**
HTTP / WebSocket / Scenario 串接 / 環境變數 / Auth (Bearer・API Key・Login) /
Retry + Backoff / Response 驗證 (regex・type・len・exists) / Tags 過濾 /
Debug Log / JSON+HTML 報告 / 檔案上傳 / 獨立匯出

---

## 三、使用方式

```bash
# 安裝
pip install -r requirements.txt

# 執行所有測試
python run_tests.py

# 常用指令
python run_tests.py --generate-only              # 只產生不執行
python run_tests.py --api-file api_definitions/example_http.yaml  # 單一檔案
python run_tests.py -v --debug                   # 詳細日誌
python run_tests.py --tags read --skip-tags write # Tag 過濾
python run_tests.py --html                        # HTML 報告
python run_tests.py --export generated_tests/test_xxx.py  # 匯出獨立腳本

# 環境變數切換
API_BASE_URL=https://staging.api.com API_TOKEN=xxx python run_tests.py
```

---

## 四、請 AI 實作新測試

告訴 AI 以下資訊，即可自動完成：

| 你需要提供 | 範例 |
|-----------|------|
| API base URL | `https://api.example.com` |
| 要測試的 endpoints | `GET /users`, `POST /users`, `DELETE /users/:id` |
| 認證方式 | Bearer Token / API Key / Login |
| 預期的 response 狀態碼 | 200, 201, 204 |
| 需要驗證的欄位 | `data` 是 array、`total` 是 integer |
| 測試數量 / 資料筆數 | 5 組測試資料 |
| 是否需要 Scenario 串接 | 建立 → 查詢 → 刪除 |
| 環境變數 | `API_TOKEN`, `API_BASE_URL` |

AI 會依照 CLAUDE.md 中的規範自動：
1. 開分支 → 2. 寫 YAML 定義 + 測試資料 → 3. 跑測試（失敗自動 retry 3 次）→ 4. Code Review → 5. 請你 Review
