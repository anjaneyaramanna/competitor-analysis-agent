# Multi-Agent Competitor Analysis

A Streamlit and Jupyter project that uses Python, LangGraph, the You.com Research API and SQLite checkpoints to research one target company. It discovers three relevant competitors, gathers current evidence, structures cited findings, checks the evidence and lets the user inspect one competitor at a time.

![Architecture](competitor_analysis_architecture.png)

## Features

- Enter any target company, market context and news window in Streamlit.
- Explicit LangGraph stages: plan, discover, collect, extract, critic and compile.
- You.com-only web/news research and synthesis with bounded retries and source tracking.
- No OpenAI dependency, API key or model call.
- Python-based evidence normalization, citation checks and final summary formatting.
- SQLite checkpoints for inspection and resume.
- Readable saved-run labels and a one-competitor results view.
- Markdown and JSON downloads for the selected competitor.
- Clearly labeled simulator when the You.com credential is absent.

## Setup

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and configure `YOU_API_KEY`. Never commit `.env`.
4. Start the interface:

   ```powershell
   python -m streamlit run streamlit_app.py
   ```

5. Open the localhost URL printed by Streamlit, enter a target company and run the research.

The notebook contains the same workflow with step-by-step diagrams and logs:

```powershell
jupyter lab competitor_analysis.ipynb
```

## Result flow

One target company is researched per run. The workflow retains three discovered competitors for evidence and traceability. The UI displays only the competitor selected in the dropdown.

## Agent roles

The architecture has five logical agent roles:

1. **Competitor Research Orchestrator** — creates the plan, controls LangGraph routing and compiles the briefing with Python.
2. **Discovery Agent** — asks the You.com Research API for three evidence-supported competitors.
3. **Evidence Agent** — asks You.com for pricing, features, positioning and recent news for each competitor.
4. **Analysis Agent** — normalizes You.com's structured results into cited competitor records with Python.
5. **Critic Agent** — validates source IDs and news dates with deterministic Python checks.

Planning and compilation are two tasks performed by the same orchestrator. The Evidence Agent role runs once for each discovered competitor.

## Credentials and provider

The You.com credential loads from the project `.env` first and is never printed. Generated results, logs and SQLite databases stay under `.research_runs/`, which is excluded from Git.

`YOU_RESEARCH_EFFORT` accepts `standard`, `deep` or `exhaustive`. The project defaults to `standard`; You.com's structured output is unavailable with `lite`. Live runs may incur You.com provider charges.
