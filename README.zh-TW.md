# BoundaryLoop

[架構圖](README.md#architecture) · [English](README.md)

以人類授權為邊界的 coding agent 控制器：限制重試、帶著證據升級問題，並從 checkpoint 繼續工作。

Coding agent 有時會反覆修改同一個失敗的測試。先給它一份更好的計畫，也不一定能避免卡住。
BoundaryLoop 限制 Worker 的嘗試次數，保存現有成果，再把具體問題交給 Architect 模型或人類。

```text
$ boundaryloop demo
MOCK DEMO: deterministic fixture responses; real controller and Python verifier
WORKER [mock / mock-worker] implementation
VALIDATOR: FAIL (attempt 1)
RETRY: one bounded repair remains before escalation
WORKER [mock / mock-worker] implementation
VALIDATOR: FAIL (attempt 2)
STOP: ... checkpoint preserved; ticket <id>
ARCHITECT [mock / mock-architect] diagnosis
WORKER [mock / mock-worker] implementation
VALIDATOR: PASS (attempt 3)
```

在原始碼目錄安裝：`python -m pip install .`。需要 Python 3.11 以上，沒有執行期相依套件。
**v0.1.0 是實驗性版本。** [English](README.md)

## 示範

```sh
boundaryloop demo --directory demo-repair
boundaryloop demo --directory demo-decision --scenario human
boundaryloop --root demo-decision decisions
```

範例修復 port parser，同時保留 `parse_port(value)` 介面。初始實作誤收布林值與超出範圍的 port；
兩次驗證失敗後，控制器建立 ticket，Architect 提供修復步驟，Worker 再修改並通過 Python 測試。

另一個情境提出修改 `api.py` 的範圍擴張。控制器會先停下來，讓人類決定。在自己的終端拒絕後，
可沿用原合約繼續：

```sh
boundaryloop --root demo-decision decision reject DECISION_ID
# 在終端輸入畫面要求的完整確認字串。
boundaryloop --root demo-decision resume RUN_ID
```

**模型回應是確定性的 Mock；控制器、檔案檢查與 Python 驗證則實際執行。**
這不是模型能力或成本的實測。每次示範請使用全新的目錄。
[錄製方式](docs/assets/README.md) · [架構](docs/ARCHITECTURE.md)

## 為什麼做這個工具

這個專案處理的是計畫與實作之間的落差。Worker 即使照著合理計畫工作，仍可能遇到無法判斷的問題。
此時需要的是停下來、保留證據並問對問題，而不是自動批准下一次修改。

BoundaryLoop 用 Python 管理這個流程，不把可靠性寄託在更長的 prompt 上。
它沒有宣稱發明 human-in-the-loop。[相關專案與重疊功能](docs/COMPETITIVE_ANALYSIS.md)。

## 運作方式

- **Easy：**人類決定範圍 → Worker → 確定性驗證。
- **Hard：**人類決定範圍 → Architect 拆成有界子任務 → Worker → 驗證。
- 預設同一計畫下失敗兩次就停止，交給 Architect 診斷。修復計畫必須有具體步驟與再次停止的條件。
  若由 Architect 接手實作，會真正呼叫其設定的模型。
- 沒有新程式變更或失敗證據的相同升級會被擋下。重規劃、呼叫次數與執行時間也有上限。
  Worker 自稱完成，不能讓狀態變成已驗證通過。

模型只能提出結構化檔案內容。控制器先檢查整份提案的精確路徑範圍，才會寫入。
合約版本、checkpoint、重試計數、決策與執行收據都由控制器管理；模型不能替換驗證命令。

## 人類決策

局部實作由 Worker 判斷；範圍內的困難修復交給 Architect。擴張可修改檔案或增加預算，需要人類。
需求矛盾、安全取捨或新介面若超出既有驗證可表達的內容，必須另建經人類審查的合約。

```sh
boundaryloop decisions
boundaryloop decision show DECISION_ID
boundaryloop decision approve DECISION_ID --option allow-files
boundaryloop decision reject DECISION_ID
boundaryloop decision defer DECISION_ID
boundaryloop decision revoke DECISION_ID
boundaryloop resume RUN_ID
```

決策卡列出證據、已嘗試的方法、影響檔案、有效選項、後果與安全預設。佇列依優先順序集中顯示獨立決策，
每筆授權仍須個別確認，沒有一鍵全部放行。

批准需要原執行者的 OS 身分、真正的互動終端，以及完整確認字串。環境變數、管線輸入、模型產生的檔案
都不是授權。記錄綁定任務、合約、設定與 checkpoint；重大變更使舊授權失效。拒絕會保留原範圍，
撤銷會阻止後續執行但不回滾檔案。沒有人回覆時維持 `HUMAN_REQUIRED`。

## 安裝

從 GitHub 取得原始碼：

```sh
git clone https://github.com/ncusspm25/boundaryloop.git
cd boundaryloop
python -m venv .venv
# macOS/Linux: . .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install .
boundaryloop --help
boundaryloop doctor
```

此版本沒有發布到 PyPI。可以用 `python -m build` 自行建立 wheel；請遵循現有的套件與網路安裝安全規則。

## 快速開始

```sh
mkdir parser-work
boundaryloop --root parser-work init --demo
boundaryloop --root parser-work start --difficulty easy --task "Fix the parser bug"
boundaryloop --root parser-work status
```

在自己的專案先執行 `boundaryloop init`，參考
[範例合約](examples/port-parser/task-contract.json) 建立 `task-contract.json`，再設定真正的 provider。
使用精確檔名、不可修改的既有測試，以及 argv 陣列形式的驗證命令；不要提供 shell 字串。
`{python}` 代表目前的 Python。非互動環境必須明確傳入 `--difficulty easy` 或 `hard`；互動模式會詢問。

`--root`、`--json` 放在子命令前面。退出碼：`0` 完成／查詢、`2` 輸入或執行錯誤、`3` 需要人類、
`4` 已阻擋、`5` 已取消、`6` 失敗、`7` 尚未完成。

## 設定

設定儲存在不提交的 `.boundaryloop/config.json`，預設使用 Mock。請自行指定帳號支援的模型 ID：

```sh
boundaryloop config set architect.provider codex
boundaryloop config set architect.model YOUR_ARCHITECT_MODEL
boundaryloop config set worker.provider codex
boundaryloop config set worker.model YOUR_WORKER_MODEL
boundaryloop config set external_context_authorized true
boundaryloop start --difficulty hard --contract task-contract.json
```

最後一個設定代表允許把限定範圍的任務內容送到 provider。雲端執行不等於離線或私密。
Codex adapter 真正呼叫 `codex exec --model ... --sandbox read-only --output-schema ...`，
沿用本機登入與安全設定。每次交接建立新的有限對話；BoundaryLoop 的 resume 並不是原生 Codex 對話續接。

預設每個計畫最多兩次失敗嘗試、每個 run 最多兩次強模型重規劃、12 次模型呼叫、600 秒有效執行時間、
每次 provider 120 秒、每個驗證命令 30 秒。任務合約的 retry/replan 限制優先；範例初始化會帶入預設值。
等待人類的時間不計入。未取得帳務證據的成本保持 `null`；目前只有呼叫／時間上限，沒有金額硬上限。

本機失敗記憶預設開啟，遙測與能力統計預設關閉。可使用 `memory --clear`、`profile --reset`、
`config set learning false` 管理資料。統計只顯示實際驗證結果與樣本，不保證模型能力。

從 `main` 安裝 CLI 後，可以將 Skill 加到個人目錄，讓所有專案都能找到它。

```powershell
boundaryloop skill install --destination (Join-Path $env:USERPROFILE '.agents/skills/boundaryloop')
```

```sh
boundaryloop skill install --destination "$HOME/.agents/skills/boundaryloop"
```

只在單一專案使用時，執行以下命令。

```sh
boundaryloop --root /path/to/repository skill install
```

安裝後，在 Codex 選 `$boundaryloop`，例如「用 `$boundaryloop` 查看目前的 run 和待處理的決策」。
套件的呼叫設定要求明確選用 Skill。請在 Codex 使用的環境備妥 CLI。如果清單還沒出現，重新啟動 Codex。
[架構圖](README.md#architecture) · [Runtime 支援狀態與官方來源](docs/RUNTIME_SUPPORT.md)

## 目前不做的事

- **尚無完整 runtime 強制模式。**控制器會實際檢查寫入與授權，但未攔截所有原生工具、MCP、網路與驗證子程序。
  `mode=enforced` 會被拒絕；Skill 本身只是流程指引。
- 驗證命令使用主機權限執行。對不信任的程式碼，請搭配既有 OS／容器沙箱；勿提供正式環境憑證。
- 不會自動證明任意修改符合文字需求。請把 invariant 寫成確定性測試，放在 Worker 可改範圍之外。
- 沒有自動 reset、merge、部署、刪除或執行模型自選 shell 命令，也沒有無人值守的批准 API。
  檔案漂移或不明的中斷結果需要人類處理。
- Claude Code adapter 是實驗性功能，需要原生執行檔，尚未完成 live test。
  沒有網頁儀表板、雲端協作或多使用者身分服務。

## Benchmark

```sh
boundaryloop benchmark --repetitions 3
boundaryloop benchmark --report
```

離線 harness 以相同 parser 初始內容，隔離執行 strong-only、strong-plan/weak-worker 與 BoundaryLoop 策略，
產生 JSON、CSV、Markdown。模型是確定性 fixture；只能展示停止與恢復，不能證明省錢或模型能力差異。
尚未完成可比較的 live model benchmark。無法量測的 token、成本與升級準確率為 `null`。
[方法](benchmarks/README.md) · [實際驗證紀錄](docs/VERIFICATION.md)

## 開發

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build --no-isolation
```

測試不需要付費 API。選用的 live smoke 與 Skill discovery 腳本在 `scripts/`。
[CONTRIBUTING.md](CONTRIBUTING.md) 列出適合入門的小任務。

## 參與及授權

歡迎提供可重現問題、合約與去識別化驗證證據。請勿公開私人資料庫或原始對話。
回報安全問題前請看 [SECURITY.md](SECURITY.md)。程式以 [MIT](LICENSE) 授權。
