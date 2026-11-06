.PHONY: install data train api test notebook all
install:   ; pip install -r requirements.txt
data:      ; python -m backend.generate_data --n 10000
train:     ; python -m ml.lookalike
api:       ; uvicorn backend.api:app --reload --port 8000
test:      ; node tests/scoring.test.js && python -m pytest -q tests
notebook:  ; jupyter nbconvert --to notebook --execute --inplace notebooks/analise.ipynb
all: data train test
