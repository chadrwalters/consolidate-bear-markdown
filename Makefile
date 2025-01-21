.PHONY: install test lint typecheck clean

install:
	uv pip install -e ".[dev]"

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run black --check .

typecheck:
	uv run mypy src tests

clean:
	rm -rf .cbm/*.log
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
