# Repository instructions

- Use [`uv`](pyproject.toml) for local commands and test execution.
- Run targeted tests with [`uv run pytest`](pyproject.toml), for example `uv run pytest tests/test_command_line_utils.py -k <pattern> -vv`.
- Prefer focused regression tests in [`tests/test_command_line_utils.py`](tests/test_command_line_utils.py) and [`tests/test_optimization.py`](tests/test_optimization.py) before broader test runs.
- Keep changes minimal and aligned with existing project conventions in [`pyproject.toml`](pyproject.toml) and the test suite under [`tests/`](tests).
