# CLAUDE.md — AI 開發規範

本文件定義 AI 在此專案中的開發流程、程式碼品質要求、測試規範。
**所有 AI 操作必須嚴格遵守以下規則。**

---

## 一、開發流程（必須依序執行）

```
1. 收到需求
      │
2. 開 feature branch（從 main 分出）
      │
3. 規劃需求（列出方案、影響範圍、檔案清單）
      │
4. 開始開發
      │
5. 自動跑測試（unit test / pytest）
      │  ├─ 失敗 → 自行分析原因 → 修正 → 重跑（最多 retry 3 次）
      │  └─ 3 次都失敗 → 仍按流程走，將錯誤報告提交 review
      │
6. Code Review（AI 自檢）
      │
7. 提交給使用者 Review
      │  ├─ 使用者不同意 → 回到步驟 4 繼續開發
      │  └─ 使用者同意 → 進入步驟 8
      │
8. Merge to main（需使用者明確同意）
```

### 規則

- **每個需求必須開新分支**，禁止直接在 main 上開發
- **開發前必須先規劃**，說明要改什麼、為什麼、影響哪些檔案
- **未經使用者同意，禁止 merge / push to main**
- **測試失敗時必須自行修正**，不能直接跟使用者說「測試失敗了」就停下來
- 自動 retry 最多 3 次，每次 retry 前必須重新思考失敗原因，不能重複同樣的修正方式

---

## 二、程式碼品質要求

### 架構原則

每次修改程式碼都必須考慮：

1. **可維護性 (Maintainability)**
   - 命名清楚、職責單一
   - 避免 god function / god class
   - 相關邏輯放在一起，不相關的分開

2. **可擴充性 (Extensibility)**
   - 新增功能不應大量修改既有程式碼
   - 使用明確的介面和抽象
   - 設定與邏輯分離

3. **可讀性 (Readability)**
   - 程式碼本身就是文件，變數名和函式名要能說明用途
   - 複雜邏輯才加註解，解釋「為什麼」而非「做什麼」
   - 保持一致的程式碼風格

### 禁止事項

- 禁止寫出有安全漏洞的程式碼（injection、XSS、硬編碼密碼等）
- 禁止過度工程化（不要為了「未來可能」加功能）
- 禁止忽略錯誤處理（在系統邊界必須做驗證）
- 禁止複製貼上大段重複程式碼，但也不要為了一次使用就過度抽象

---

## 三、測試規範

### AI 實作測試時的流程

當使用者要求實作新測試，AI 必須：

1. **詢問使用者提供以下資訊**（缺什麼問什麼，不要猜）：

   | 必要資訊 | 說明 |
   |---------|------|
   | API base URL | 目標 API 的基礎網址 |
   | Endpoints 清單 | 要測試哪些 API（method + path） |
   | 認證方式 | Bearer / API Key / Login / 無 |
   | 預期狀態碼 | 每個 endpoint 期望的 HTTP status |
   | 驗證欄位 | 需要檢查的 response 欄位和規則 |
   | 測試資料數量 | 需要幾組 parametrize 測試資料 |
   | 是否需要 Scenario | 多 API 串接流程 |
   | 環境變數 | 需要哪些環境變數 |

2. **收集完資訊後自動執行**：
   - 產生 YAML API 定義檔到 `api_definitions/`
   - 產生測試資料到 `test_data/`（如需要）
   - 執行 `python run_tests.py` 驗證
   - 失敗時自行分析並修正，最多 retry 3 次
   - 每次 retry 必須用不同策略，不能重複同樣的嘗試

3. **測試通過後**：
   - 進行 Code Review 自檢
   - 提交給使用者 Review

### 測試執行規則

```bash
# 基本測試
python run_tests.py

# 指定檔案測試
python run_tests.py --api-file api_definitions/<file>.yaml -v

# Debug 模式（測試失敗時使用）
python run_tests.py --api-file api_definitions/<file>.yaml -v --debug
```

- 所有新增的 API 定義都必須能通過 `python run_tests.py` 執行
- 測試必須是可重複執行的（不依賴外部狀態或執行順序）

### Tag 命名規則

每個測試案例的 tags 必須包含**專屬 tag**（第一個）+ 分類 tags：

```yaml
tags: ["<endpoint_name>", "<操作類型>", "<資源類型>"]
```

- **第一個 tag = endpoint name**（專屬，用於單獨執行該測試）
- 後續 tags = 分類用途（`read` / `write` / `posts` / `wss` / `scenario` 等）

範例：
```yaml
# HTTP
tags: ["list_posts", "read", "posts"]
tags: ["create_post", "write", "posts"]

# WSS
tags: ["echo_text", "wss", "echo"]

# Scenario
tags: ["create_then_comment", "scenario", "flow"]
```

用法：
```bash
# 跑單一測試案例
python run_tests.py --tags list_posts

# 跑整個分類
python run_tests.py --tags read
```

---

## 四、Git 規範

### 分支命名

```
feature/<功能描述>     # 新功能
fix/<問題描述>         # 修復
refactor/<描述>        # 重構
test/<描述>            # 純測試
```

### Commit Message 格式

```
<type>: <簡短描述>

<詳細說明（可選）>
```

type 類型：
- `feat`: 新功能
- `fix`: 修復
- `refactor`: 重構（不改變行為）
- `test`: 測試相關
- `docs`: 文件
- `chore`: 雜項（設定、依賴更新）

### 禁止操作

- 禁止 `git push --force` to main
- 禁止 `git reset --hard` 未經使用者同意
- 禁止跳過 pre-commit hooks（`--no-verify`）
- 禁止直接 push to main，必須經過 review 流程

---

## 五、Code Review 檢查清單

AI 在提交給使用者 Review 前，必須自行檢查以下項目：

### 功能面
- [ ] 是否完成需求的所有要求
- [ ] 邊界情況是否處理
- [ ] 錯誤處理是否適當

### 程式碼品質
- [ ] 命名是否清楚、一致
- [ ] 是否有重複程式碼可以合理抽取
- [ ] 是否符合既有程式碼風格
- [ ] 是否有不必要的複雜度

### 測試面
- [ ] 測試是否通過
- [ ] 測試是否覆蓋主要路徑
- [ ] 測試資料是否合理

### 安全面
- [ ] 是否有硬編碼的密碼或 token
- [ ] 是否有 injection 風險
- [ ] 環境變數是否正確使用

---

## 六、專案結構規則

```
api_definitions/     → API 定義檔（YAML/JSON）
test_data/           → 測試資料（與定義解耦合）
api_test/core/       → 解析器、資料載入器
api_test/executors/  → HTTP / WSS 執行器
api_test/exporters/  → 獨立腳本匯出器
api_test/generators/ → pytest 自動產生器
generated_tests/     → 自動產生的測試（git ignored）
exports/             → 匯出的獨立腳本（git ignored）
reports/             → 測試報告（git ignored）
```

### 新增檔案規則

- 新的 API 定義 → `api_definitions/`
- 新的測試資料 → `test_data/`
- 新的核心模組 → 放到 `api_test/` 對應子目錄
- 禁止在根目錄隨意新增檔案
- 遵循既有的模組劃分方式
