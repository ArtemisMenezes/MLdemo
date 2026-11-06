# Projeto ML

A standalone B2B prospecting demo. Define an ideal customer profile (ICP), qualify companies, track opportunities in a CRM, and discover businesses that resemble simulated customers.

This demo illustrates a small part of the platform at the company where I work. I started from an existing project, refined the interface, and implemented the Copilot, SQL-based ICP search, and machine learning recommendations for similar companies.

**All data is synthetic.** Companies, Brazilian tax IDs (CNPJs), deals, and customer labels were generated for the demo.

## What to try

1. **Search + ICP.** Change the industry code (CNAE), state, or company size. Select **Por quê?** to see which criteria contributed to the score. Missing values appear as unknown.
2. **CRM.** Add companies, move opportunities through stages, and log activities.
3. **Copilot.** Review rule-based follow-up suggestions. A suggestion becomes a task after you approve it.
4. **Metrics.** Explore the funnel, acceptance by salesperson, and time spent in each stage.
5. **Similar companies (ML).** Explore companies that resemble simulated customers and see what drove each recommendation.

## Run locally

With Python 3.10 or later installed, open PowerShell in the directory containing `requirements.txt` and run the following commands.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --port 8000
```

Open the [local demo](http://localhost:8000) or the [interactive API docs](http://localhost:8000/docs). The SQLite database and model artifacts are included. The interface is in Brazilian Portuguese.

You can also open `index.html` directly to try the static mode with 40 companies. The API-backed mode searches 10,000 companies and enables the **Similares (ML)** tab.

## How the ICP score and model work

The **ICP score** measures how closely a company matches configurable criteria. In API-backed mode, SQL computes the score, and the interface explains which criteria matched, failed to match, or had missing data. The **lookalike model** uses logistic regression to rank companies based on signals associated with simulated customers.

Evaluation used out-of-fold predictions from five stratified folds. Of 8,694 active companies, 505 carried the simulated customer label.

| Approach | ROC AUC | Precision@100 |
| --- | ---: | ---: |
| Logistic regression | 0.749 | 24% |
| Gradient boosting | 0.732 | 24% |
| ICP rules | 0.735 | 24% |
| Random selection | 0.500 | 5.8% expected |

Logistic regression had a modest AUC advantage over the ICP rules, and both approaches had the same precision among the top 100 results. The evaluation demonstrates that the pipeline works on synthetic data. Performance on real data remains untested.

## Project layout

| Path | Purpose |
| --- | --- |
| `index.html`, `app.js`, `scoring.js` | JavaScript interface with no build step |
| [backend/api.py](backend/api.py) and [backend/sql](backend/sql) | FastAPI endpoints, SQLite search, and metrics |
| [backend/generate_data.py](backend/generate_data.py) | Synthetic data generation with pandas |
| [ml/lookalike.py](ml/lookalike.py) | Model training and evaluation with scikit-learn |
| [notebooks/analise.ipynb](notebooks/analise.ipynb) | Executed notebook covering data quality, SQL, and model evaluation |

## Tests and reproducibility

With Node.js 18 or later and the Python dependencies installed, run the test suites from the project directory.

```powershell
node tests/scoring.test.js
.\.venv\Scripts\python.exe -m pytest -q tests
```

To regenerate the data and train the model, run the following commands.

```powershell
.\.venv\Scripts\python.exe -m backend.generate_data --n 10000
.\.venv\Scripts\python.exe -m ml.lookalike
```

The [Makefile](Makefile) also provides targets for running, testing, and rebuilding the demo.

## License

[MIT](LICENSE).
