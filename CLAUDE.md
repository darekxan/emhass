# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EMHASS (Energy Management for Home Assistant) uses Linear Programming (via CVXPY + HiGHS solver) to optimize home energy dispatch — scheduling batteries, deferrable loads, and thermal systems to minimize cost or maximize profit given solar forecasts, electricity prices, and Home Assistant sensor data.

## Commands

```bash
# Install dependencies
uv sync --extra test

# Run all tests
uv run pytest

# Run specific test file (preferred approach)
uv run pytest tests/test_command_line_utils.py -k <pattern> -vv

# Run the web server
python3 ./src/emhass/web_server.py

# Lint and format
ruff check --fix src/
ruff format src/
```

Prefer focused regression tests in `tests/test_command_line_utils.py` and `tests/test_optimization.py` before broader test runs.

## Architecture

### Core Data Flow

```
Home Assistant REST API
    → RetrieveHass (retrieve_hass.py)      # fetch sensor history
    → utils.build_params()                  # build config/parameters
    → Forecast (forecast.py)               # PV, load, price forecasts
    → Optimization (optimization.py)       # LP solver
    → publish_data (command_line.py)       # post results back to HA
```

### Key Modules

| Module | Role |
|--------|------|
| `web_server.py` | Quart async ASGI server (port 5000); routes to command_line |
| `command_line.py` | Orchestration layer: sets up context, calls forecast + optimization + publish |
| `optimization.py` | Core LP problem builder and solver (CVXPY + HiGHS/CBC) |
| `forecast.py` | PV forecasting (Open-Meteo, SolCast, PVLib), load forecasting (naive/ML), price forecasting |
| `retrieve_hass.py` | Home Assistant REST/WebSocket client |
| `utils.py` | Configuration loading, data preprocessing, parameter building |
| `machine_learning_forecaster.py` | SKForecast-based time-series ML models |
| `optimization_unified_thermal.py` | Thermal balance constraints (heating/cooling signed model) |

### Key Abstractions

- **`SetupContext`** — bundles configuration + utilities needed before optimization runs
- **`PublishContext`** — bundles data for publishing results to Home Assistant
- **`OptimizationCache`** / **`OptimizationCacheKey`** — thread-safe warm-start cache for repeated MPC optimizations; invalidated by structural config changes
- **`Forecast`** — unified interface across all forecast sources
- **`Optimization`** — wraps CVXPY problem construction for battery, deferrable loads, and thermal constraints

### Optimization Structure

The LP in `optimization.py` handles:
- Battery charge/discharge with SoC constraints
- Deferrable loads (on/off scheduling with minimum runtime)
- Thermal battery (heating/cooling with building physics)
- Cost minimization or profit maximization objective
- **Billing-window netting** (`netting_window_time_steps > 1`): groups consecutive timesteps into billing windows and nets grid import vs. export within each window before pricing (e.g. Polish OZE prosumer regulations). Adds `P_autoconsumption` column to results.
- **Deferrable load running overhead** (`set_deferrable_load_running_overhead`): per-load static cost (W) penalizing each active timestep, biasing LP toward fewer/longer run sessions.

Thermal extensions live in `optimization_unified_thermal.py` using a signed thermal balance model (positive = heating, negative = cooling).

### CVXPY Parameters vs. Structural Decisions

Some optimization inputs are stored as `cp.Parameter` objects (mutable at solve-time without rebuilding the problem) rather than Python constants. This is critical for cache compatibility — changing a `cp.Parameter` value keeps the warm-start cache valid, while changing a structural decision (e.g. number of loads, boolean constraints) invalidates it.

Current `cp.Parameter` items:
- `param_min_power` — per-load minimum power (`minimum_power_of_deferrable_loads`)

When adding new tunable knobs, prefer `cp.Parameter` over rebuilding the CVXPY problem if the constraint graph shape doesn't change.

### Configuration

- `src/emhass/data/config_defaults.json` — canonical defaults for all parameters
- `src/emhass/data/associations.csv` — maps parameter names to config categories
- `src/emhass/data/unified_thermal_schema.json` — JSON schema for thermal balance configurations
- `options.json` — Home Assistant add-on runtime config (hass_url, token, location)
- `secrets_emhass.yaml` — secrets for standalone/Docker deployment

Notable recent parameters:
| Parameter | Default | Purpose |
|-----------|---------|---------|
| `netting_window_time_steps` | 1 | Sub-hourly billing window size; >1 enables per-window net import/export pricing |
| `set_deferrable_load_running_overhead` | [0.0, …] | Per-load W cost penalizing each active timestep |
| `minimum_power_of_deferrable_loads` | [0.0, …] | Per-load minimum power when active (now a `cp.Parameter`) |

### Test Structure

Tests use `unittest.mock` (AsyncMock, MagicMock, patch) and `aioresponses` for async HTTP mocking. Test data uses pickle files under `data/`. Path resolution uses `utils.get_root(__file__, num_parent=2)`.

## Code Conventions

- **Async-first**: LP solver (CVXPY) is inherently sync; all I/O and orchestration in `command_line.py` is async (30+ async functions). Never add `asyncio.run()` inside async call chains.
- **Logging**: Use the `logger` passed via context objects. Never use `print()`.
- **Error handling**: Wrap external calls (HA API, solver) in try/except; log with `logger.error()`. Custom exception hierarchy in `websocket_client.py`: `WebSocketError → AuthenticationError / ConnectionError / RequestError`.
- **Line length**: 100 chars (Ruff-enforced). Run `ruff check --fix src/` before committing.
- **Immutability**: Cache keys use `@dataclass(frozen=True)` so they are hashable; do not store mutable state in them.
- **Commit style**: `feat:`, `fix:`, `refactor:`, `perf:`, `docs:`, `test:` conventional commits.
- **Per-load list parameters**: When adding a new per-load parameter, use `check_def_loads()` in `utils.treat_runtimeparams()` to validate the list length matches `number_of_deferrable_loads`.
- **ML forecaster horizon**: Pass `prediction_horizon` in the runtime payload to control the number of forecast steps returned by `forecast_model_predict`. It is forwarded as `steps` to `MLForecaster.predict()`.

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `python-test.yml` | push/PR | pytest on Ubuntu/macOS/Windows × Python 3.10–3.12 |
| `code-quality.yml` | push/PR | Ruff lint + format check |
| `codeql.yml` | push/PR | Security scanning |
| `docker-build-test.yaml` | push/PR | Docker image build verification |
| `publish_docker.yaml` | release tag | Push multi-arch image to Docker Hub |
| `upload-package-to-pypi.yaml` | release tag | Publish to PyPI |

## Quick Reference

| I want to... | Look at... |
|--------------|-----------|
| Add an LP constraint | `optimization.py` — find the relevant `perform_*_optim` method |
| Add a forecast source | `forecast.py` — follow the existing `get_forecast_*` pattern |
| Add a REST endpoint | `web_server.py` — add Quart route, wire to `command_line.py` function |
| Change a default parameter value | `src/emhass/data/config_defaults.json` |
| Add a new config parameter | `config_defaults.json` + `associations.csv` + `utils.build_params()` |
| Add thermal constraints | `optimization_unified_thermal.py` |
| Add regression tests | `tests/test_command_line_utils.py` or `tests/test_optimization.py` |
| Debug HA connectivity | `retrieve_hass.py` + `websocket_client.py` |
| Add a per-load parameter | `config_defaults.json` + `associations.csv` + `utils.treat_runtimeparams()` (`check_def_loads()`) |
| Make a param cache-friendly | Use `cp.Parameter` in `optimization.py`; assign `.value` before each solve |
| Add billing-window netting logic | `optimization.py` — `_add_netting_window_constraints()` + objective section |
