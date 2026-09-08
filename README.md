# Multi-Agent Competitor Analysis

A Streamlit and Jupyter project that uses Python, LangGraph, OpenAI, You.com Search and SQLite checkpoints to research one target company. The workflow discovers three relevant competitors, gathers current evidence, extracts structured findings, runs a critic review and lets the user inspect one competitor at a time.

![Architecture](competitor_analysis_architecture.png)

## Features

- Enter any target company, market context and news window in Streamlit.
- Explicit LangGraph stages: plan, discover, collect, extract, critic and compile.
- You.com web/news research with bounded retries and source tracking.
- OpenAI structured extraction and critic review.
- SQLite checkpoints for inspection and resume.
- Readable saved-run labels and a one-competitor results view.
- Markdown and JSON downloads for the selected competitor.
- Clearly labeled simulator when required credentials are absent.

## Setup

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and configure `OPENAI_API_KEY` and `YOU_API_KEY`. Never commit `.env`.
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

## Credentials and safety

Credentials load from the project `.env` first and are never printed. Generated results, logs and SQLite databases stay under `.research_runs/`, which is excluded from Git. Live research uses external APIs and may incur provider charges.
