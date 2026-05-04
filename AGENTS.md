# Repository Guide

This file is a lightweight guide for AI assistants and contributors working in this
repository. Treat it as orientation, not as a substitute for reading the code, tests,
and project documentation around the change you are making.

## Project Overview

EMHASS (Energy Management for Home Assistant) optimizes home energy dispatch. It
combines Home Assistant data, solar/load/price forecasts, and CVXPY-based
optimization to schedule batteries, deferrable loads, and thermal loads.

The usual flow is:

```text
Home Assistant data
  -> configuration and forecast preparation
  -> optimization
  -> publishing results back to Home Assistant
```

## Working Principles

- Keep changes focused and consistent with nearby code.
- Prefer existing project patterns over new abstractions.
- Read the relevant tests before changing behavior.
- Preserve local runtime files, secrets, generated data, and unrelated user changes.
- Add or update tests when changing behavior, especially optimizer constraints,
  configuration parsing, publishing, or Home Assistant integration.
- Keep documentation concise and durable; avoid documenting temporary investigation
  details as permanent project knowledge.

## Common Commands

Use `uv` for local commands.

```bash
uv sync --extra test
uv run pytest
uv run pytest tests/test_command_line_utils.py -k <pattern> -vv
uv run pytest tests/test_optimization.py -k <pattern> -vv
uv run ruff check src tests
uv run ruff format src tests
uv run python ./src/emhass/web_server.py
```

Prefer focused regression tests before broad runs. The most common starting points
are `tests/test_command_line_utils.py` and `tests/test_optimization.py`.

## Project Map

- `src/emhass/command_line.py`: orchestration for setup, forecasting, optimization,
  and publishing.
- `src/emhass/optimization.py`: core CVXPY optimization model.
- `src/emhass/optimization_unified_thermal.py`: thermal balance constraints.
- `src/emhass/forecast.py`: forecast providers and forecast model integration.
- `src/emhass/retrieve_hass.py`: Home Assistant data retrieval.
- `src/emhass/web_server.py`: web server routes.
- `src/emhass/utils.py`: configuration loading, validation, and preprocessing.
- `src/emhass/data/config_defaults.json`: default configuration values.
- `src/emhass/data/associations.csv`: mapping between config keys and sections.
- `tests/`: regression and integration-style tests.
- `docs/` and `examples/`: user-facing documentation and sample configuration.

## Change Checklist

Before finishing a change, check the basics:

- The change is grouped with the feature or fix it belongs to.
- New configuration keys have defaults, associations, parsing, and tests.
- Per-load configuration lists are validated against the number of deferrable loads.
- Optimization changes have regression coverage for feasibility and result columns.
- Publishing changes handle missing optional columns and failed optimizations safely.
- Ruff and the relevant focused tests pass.
