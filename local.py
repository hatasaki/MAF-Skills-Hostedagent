"""ローカル実行用エントリポイント。

使い方:
  az login                       # Azure CLI で先にログイン
  python -m venv .venv && .\\.venv\\Scripts\\Activate.ps1  # Windows
  pip install -r requirements.txt
  copy .env.example .env         # 値を編集
  python local.py
"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from orchestrator import build_orchestrator


async def main() -> None:
    load_dotenv()
    agent = build_orchestrator()

    print("Orchestrator ready. 終了するには 'exit' / 'quit' / Ctrl+C。\n")
    while True:
        try:
            user = input("User> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            break

        result = await agent.run(user)
        print(f"\nAgent>\n{result.text}\n")


if __name__ == "__main__":
    asyncio.run(main())
