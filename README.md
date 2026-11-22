# MemoGraph + Trading Agent

Multi-agent equity research (MemoGraph) that writes cited research memos, with a
trading layer on top: an LLM strategy agent proposes trades, a deterministic risk
engine approves or rejects them, and approved orders go to a paper (fake-money) account.

Status: Phase 1 (foundation) of 6.

## Run it

```bash
docker compose up -d                 # Postgres + pgvector, Redis
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ollama pull qwen3:8b
python scripts/check_setup.py        # should print three PASS lines
pytest
```
