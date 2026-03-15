PYTHON ?= python3
VENV   ?= .venv
BIN    := $(VENV)/bin

.PHONY: help venv install lint format test eval run-sample mcp clean

help:
	@echo "make install     create $(VENV) and install the package with dev extras"
	@echo "make lint        ruff + mypy --strict"
	@echo "make format      ruff format + autofix"
	@echo "make test        pytest (offline, fake LLM)"
	@echo "make eval        run golden evals (fake client; real API if ANTHROPIC_API_KEY is set)"
	@echo "make run-sample  analyze the bundled sample CSV with the fake client"
	@echo "make mcp         start the stdio MCP server"

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip

venv: $(BIN)/python

install: venv
	$(BIN)/python -m pip install -e ".[dev]"

lint:
	$(BIN)/ruff check src tests evals
	$(BIN)/ruff format --check src tests evals
	$(BIN)/mypy

format:
	$(BIN)/ruff format src tests evals
	$(BIN)/ruff check --fix src tests evals

test:
	$(BIN)/pytest

eval:
	$(BIN)/python -m decline_assistant.evals evals/cases.yaml

run-sample:
	DECLINES_LLM_BACKEND=fake $(BIN)/declines analyze samples/declines.csv --out report.md

mcp:
	$(BIN)/declines-mcp

clean:
	rm -rf $(VENV) build dist *.egg-info src/*.egg-info .mypy_cache .ruff_cache .pytest_cache report.md report.json
