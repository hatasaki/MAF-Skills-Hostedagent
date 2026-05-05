# MAF Skills × Hosted Agent ワークショップ

> Microsoft Agent Framework v1.0 以降の **Agent Skills** 機能を使い、Microsoft Foundry に登録済みの 2 つのエージェントを呼び分ける **オーケストレーションエージェント** を構築し、**Foundry Hosted Agent** としてデプロイするハンズオン。

## 構成イメージ

```
                           ┌────────────────────────────────┐
   User ──▶ Orchestrator ─▶│ ms_learn_agent (Microsoft 技術) │
            (本リポジトリ) │ web_search_agent (Web 検索)    │
                           └────────────────────────────────┘
            ▲ ルーティング判断は instructions ではなく
              skills/orchestrator-routing/SKILL.md に記述
```

| 役割 | 実体 |
| --- | --- |
| オーケストレーションエージェント | 本リポジトリの `Agent` (Foundry の LLM + Agent Skills) |
| Microsoft 技術専門家エージェント | Foundry に登録済みの既存 Prompt Agent (Microsoft Learn ベース) |
| Web 検索エージェント | Foundry に登録済みの既存 Prompt Agent (Bing Grounding 等) |
| ルーティング制御 | [`skills/orchestrator-routing/SKILL.md`](skills/orchestrator-routing/SKILL.md) (Agent Skills) |

## 前提

- [Microsoft Foundry プロジェクト](https://learn.microsoft.com/en-us/azure/foundry/how-to/create-projects) と LLM のモデルデプロイ (例: `gpt-5.2`、名前は任意)
- Foundry に登録済みの 2 つの Prompt Agent (Microsoft 技術専門家 / Web 検索)
- Python 3.10+
- [Azure CLI 2.80+](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) と `az login` 済み
- [Azure Developer CLI (azd) 1.24.0+](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd) と AI Agents 拡張: `azd ext install azure.ai.agents` / `azd auth login`
- ロール: Foundry プロジェクトに **Azure AI Project Manager** ([Step 0](#step-0-ロール権限-の確認と付与) を参照)

---

## Step 0. ロール (権限) の確認と付与

Hosted Agent を新規作成する `azd deploy` では、プラットフォームが内部で生成する Agent identity に `Azure AI User` ロールを割り当てる必要があります。この割り当てを実行できる最小権限ロールが **Azure AI Project Manager** (プロジェクトスコープ) です。  
`Azure AI User` だけでは「ロール割り当て権限」が無いため新規 Hosted Agent 作成に失敗します。

> 既に対象 Foundry プロジェクトで **Azure AI Project Manager / Azure AI Account Owner / Owner** のいずれかを保持している場合、本ステップはスキップしてください。

### A. Azure ポータルで現在の割り当てを確認

1. [Azure ポータル](https://portal.azure.com/) を開く
2. 検索バーで **Foundry プロジェクト** リソースを検索 (例: 表示名やリソースグループから絞り込み)
3. 左メニュー **「アクセス制御 (IAM)」 → 「ロール割り当て」 → 「マイ アクセスを表示」** を選択
4. 一覧に以下のいずれかがあれば OK (本ステップ完了):
   - `Azure AI Project Manager`
   - `Azure AI Account Owner`
   - `Owner`

### B. 権限が無い場合 ─ Azure ポータルで付与

サブスクリプションまたはプロジェクトの **Owner** / **User Access Administrator** に依頼するか、自身がそのロールを持つ場合に以下を実行します。

1. Foundry プロジェクトリソースの **「アクセス制御 (IAM)」** を開く
2. **「+ 追加」 → 「ロールの割り当ての追加」**
3. **役割**: `Azure AI Project Manager` を選択 → **次へ**
4. **メンバー**: 対象ユーザー (= ワークショップ受講者) を検索して追加 → **次へ**
5. **レビューと割り当て** をクリック

### C. (代替) Azure CLI で付与

#### Windows (PowerShell)

```powershell
# プロジェクトの ARM ID をコピー (Foundry ポータル → プロジェクト → JSON ビュー)
$PROJECT_ID = "<your-foundry-project-arm-id>"
$USER_OBJECT_ID = (az ad signed-in-user show --query id -o tsv)

az role assignment create `
  --assignee-object-id $USER_OBJECT_ID `
  --assignee-principal-type User `
  --role "Azure AI Project Manager" `
  --scope $PROJECT_ID
```

#### Linux / macOS (bash)

```bash
# プロジェクトの ARM ID をコピー (Foundry ポータル → プロジェクト → JSON ビュー)
PROJECT_ID="<your-foundry-project-arm-id>"
USER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)

az role assignment create \
  --assignee-object-id "$USER_OBJECT_ID" \
  --assignee-principal-type User \
  --role "Azure AI Project Manager" \
  --scope "$PROJECT_ID"
```

> 反映には数分かかる場合があります。`azd deploy` 実行時に `AuthorizationFailed` / `roleAssignments/write` 不足のエラーが出る場合は本ステップが未反映の可能性があります。

---

## Step 1. リポジトリをクローン

VS Code を開いて、本リポジトリをクローンします (Windows / Linux / macOS 共通)。

```bash
git clone https://github.com/hatasaki/MAF-Skills-Hostedagent.git
cd MAF-Skills-Hostedagent
code .
```

---

## Step 2. 既存エージェント ID と環境変数を設定

Foundry ポータルで対象プロジェクトを開き、以下を控えます。

1. **プロジェクトエンドポイント** ─ プロジェクトの「概要」ページの URL  
   形式: `https://<account>.services.ai.azure.com/api/projects/<project>`
2. **モデルデプロイ名** ─ 「モデル + エンドポイント」で確認 (例: `gpt-5.2`。デプロイした際につけた名前をそのまま使用)
3. **2 つの既存エージェントの名前 / バージョン** ─ 「エージェント」一覧から確認

`.env.example` をコピーして `.env` を作成し、エディタで編集します。

#### Windows (PowerShell)

```powershell
Copy-Item .env.example .env
notepad .env
```

#### Linux / macOS (bash)

```bash
cp .env.example .env
${EDITOR:-vi} .env
```

`.env` 例 (全項目必須 — 1 つでも未設定だと起動時にエラーとなります):

```dotenv
FOUNDRY_PROJECT_ENDPOINT=https://contoso.services.ai.azure.com/api/projects/contoso-proj
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.2

MS_LEARN_AGENT_NAME=ms-learn-expert
MS_LEARN_AGENT_VERSION=1

WEB_SEARCH_AGENT_NAME=web-search
WEB_SEARCH_AGENT_VERSION=1
```

> **メモ** ─ 上記のうち `FOUNDRY_PROJECT_ENDPOINT` / `AZURE_AI_MODEL_DEPLOYMENT_NAME` / `MS_LEARN_AGENT_NAME` / `WEB_SEARCH_AGENT_NAME` は必須です。未設定のものがあるとオーケストレータ起動時に `次の必須環境変数が未設定です: ...` というエラーが表示されます。

---

## Step 3. Agent Skills の中身を確認 → 出力フォーマットをカスタマイズ

`skills/orchestrator-routing/SKILL.md` を開きます。  
このファイルには **どのサブエージェントをいつ呼ぶかというマルチエージェント制御** が書かれています。オーケストレータ本体の `instructions` (`orchestrator.py` 内) には一切ルーティングロジックを書いていません — 制御はすべて Skill 経由です。

ここに **回答をレポート形式に統一する** 出力フォーマット節を追加して、エージェントの応答スタイルをカスタマイズします。`SKILL.md` の末尾に以下のセクションを追記して保存してください。

```markdown
## 出力フォーマット

最終回答は次のレポート形式 (Markdown) で必ず作成する。

### 概要
（質問への回答を 2〜3 文で要約）

### 詳細
（サブエージェントから得た情報を整理して記載）

### 参考情報
（参照した URL や情報源を箇条書き。なければ "なし"）
```

> 追記後、ファイルを保存するだけで反映されます (再ビルド等は不要)。

---

## Step 4. ローカル実行で動作確認

#### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
az login
python local.py
```

#### Linux / macOS (bash)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
az login
python local.py
```

対話プロンプトで以下のような質問を試して、ルーティングと出力フォーマットを確認します。

| 入力例 | 期待動作 |
| --- | --- |
| `Microsoft FoundryのHosted Agentとは何?` | `ms_learn_agent` のみ呼び出し |
| `今日の東京の天気を教えて` | `web_search_agent` のみ呼び出し |
| `Microsoft Agent Frameworkと他のフレームワークを比較して` | 両方のエージェントを呼び出して統合 |

すべての回答が **「概要 / 詳細 / 参考情報」** のレポート形式で返ってくれば成功です。

---

## Step 5. Foundry Hosted Agent としてデプロイ

最もシンプルな方法として **Azure Developer CLI (`azd`)** を使います。コンテナイメージは **ACR 上でリモートビルド** されるため、ローカルに Docker をインストールしておく必要はありません。リポジトリに同梱済みの `Dockerfile` と `agent.manifest.yaml` を `azd` がそのまま使用します。

Step 2 で作成した `.env` の値を `azd env set` に流し込むスクリプトをリポジトリに同梱しているため、変数を再入力する必要はありません。

### Windows (PowerShell)

```powershell
# 1. azd プロジェクトを初期化 (Foundry プロジェクトと結びつけ)
azd ai agent init -m .\agent.manifest.yaml

# 2. .env の値を azd 環境にコピー
.\scripts\Sync-AzdEnvFromDotenv.ps1

# 3. ビルド → ACR プッシュ → Hosted Agent バージョン作成 を一括実行
azd deploy
```

### Linux / macOS (bash)

```bash
# 1. azd プロジェクトを初期化
azd ai agent init -m ./agent.manifest.yaml

# 2. .env の値を azd 環境にコピー
chmod +x ./scripts/sync-azd-env-from-dotenv.sh
./scripts/sync-azd-env-from-dotenv.sh

# 3. ビルド → ACR プッシュ → Hosted Agent バージョン作成 を一括実行
azd deploy
```

> スクリプトは `.env` の各 `KEY=VALUE` 行を読み取り、`azd env set KEY VALUE` を順次実行します。コメント行 / 空行 / 値が空の行はスキップされます。値を変更したいときは `.env` を編集してから再実行するだけで OK です。

#### `.env` を作成していない場合 (手動で `azd env set`)

`.env` を用意していない場合や、デプロイ用に値を切り替えたい場合は、`azd env set` を直接実行して同等の登録ができます (上記スクリプトの代わりにこちらを実施)。

```bash
azd env set FOUNDRY_PROJECT_ENDPOINT       "<your-endpoint>"
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "<your-model-deployment-name>"
azd env set MS_LEARN_AGENT_NAME            "<ms-learn-agent-name>"
azd env set MS_LEARN_AGENT_VERSION         "1"
azd env set WEB_SEARCH_AGENT_NAME          "<web-search-agent-name>"
azd env set WEB_SEARCH_AGENT_VERSION       "1"
```

`azd deploy` 完了後、Foundry ポータルの **「エージェント」** 一覧に `maf-skills-orchestrator` が表示されます。

### Foundry ポータル上で応答を確認

1. Foundry ポータル ([https://ai.azure.com](https://ai.azure.com)) でプロジェクトを開く
2. 左メニュー **「エージェント」 → `maf-skills-orchestrator`** を選択
3. 右側の **Playground** で Step 4 と同じ質問を入力
4. ルーティング動作と「概要 / 詳細 / 参考情報」フォーマットの応答を確認

---

## Step 6. トレースログを確認

Hosted Agent は Application Insights に自動でトレースを送信します。Foundry ポータルから直接確認できます。

1. Foundry ポータルで `maf-skills-orchestrator` を開く
2. **「トレース (Tracing)」** タブを選択
3. 任意の実行を選んでスパンを展開
4. 以下が確認できれば、Skill 経由でマルチエージェントオーケストレーションが行われていることが分かります:
   - `chat` スパン (オーケストレータの LLM 呼び出し)
   - `tool: load_skill` (Agent Skills が `orchestrator-routing` を読み込み)
   - `tool: ms_learn_agent` および/または `tool: web_search_agent` (サブエージェント呼び出し)
   - 入出力のメッセージ詳細

> Foundry プロジェクトに紐づく Application Insights を直接開いて、より詳細な分析 (実行時間 / 失敗率 / トークン数) も可能です。

---

## クリーンアップ

Windows / Linux / macOS 共通：

```bash
azd down
```

---

## ファイル構成

```
.
├── README.md                      # 本ファイル
├── .env.example                   # 環境変数テンプレート
├── requirements.txt               # Python 依存
├── .dockerignore                  # .env など秘密情報をイメージに焼き込ませない
├── Dockerfile                     # Hosted Agent 用 (linux/amd64, port 8088)
├── agent.manifest.yaml            # azd デプロイ用マニフェスト
├── orchestrator.py                # オーケストレータ構築 (Agent + Skills + as_tool)
├── local.py                       # ローカル CLI エントリポイント
├── main.py                        # Hosted エントリポイント (ResponsesHostServer)
├── scripts/
│   ├── Sync-AzdEnvFromDotenv.ps1  # .env → azd env set (Windows)
│   └── sync-azd-env-from-dotenv.sh # .env → azd env set (Linux / macOS)
└── skills/
    └── orchestrator-routing/
        └── SKILL.md               # マルチエージェント制御スキル (Agent Skills)
```

## 参考ドキュメント

- [Agent Skills (Python)](https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-python)
- [Foundry Hosted Agents (Python)](https://learn.microsoft.com/en-us/agent-framework/hosting/foundry-hosted-agent)
- [Deploy a hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent)
- [`FoundryAgent` / `FoundryChatClient`](https://learn.microsoft.com/agent-framework/agents/providers/microsoft-foundry?pivots=programming-language-python)
- [公式サンプル: `agent-framework/python/samples/04-hosting/foundry-hosted-agents`](https://github.com/microsoft/agent-framework/tree/main/python/samples/04-hosting/foundry-hosted-agents)
