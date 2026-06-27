PYTHON ?= python3
VENV   ?= .venv
BIN    := $(VENV)/bin

.PHONY: help venv install lint format test eval eval-live run-sample mcp clean

help:
	@echo "make install     create $(VENV) and install the package with dev extras"
	@echo "make lint        ruff + mypy --strict"
	@echo "make format      ruff format + autofix"
	@echo "make test        pytest (offline, fake LLM)"
	@echo "make eval        run golden evals with the offline analyst"
	@echo "make eval-live   same evals against Claude (needs ANTHROPIC_API_KEY)"
	@echo "make run-sample  analyze the bundled sample CSV with the fake client"
	@echo "make mcp         start the stdio MCP server"

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip

venv: $(BIN)/python

install: venv
	$(BIN)/python -m pip install -e ".[dev]"

lint:
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests
	$(BIN)/mypy

format:
	$(BIN)/ruff format src tests
	$(BIN)/ruff check --fix src tests

test:
	$(BIN)/pytest

eval:
	$(BIN)/python -m decline_assistant.evals evals/cases.yaml

eval-live:
	$(BIN)/python -m decline_assistant.evals evals/cases.yaml --live

run-sample:
	$(BIN)/declines analyze samples/declines.csv --out report.md --offline

mcp:
	$(BIN)/declines-mcp

clean:
	rm -rf $(VENV) build dist *.egg-info src/*.egg-info .mypy_cache .ruff_cache .pytest_cache report.md report.json
