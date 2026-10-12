"""Keep the benchmark task fixtures out of the repo's own test suite.

Each folder under `fixtures/` is an intentionally broken/incomplete sandbox
project whose `test_*.py` files are *meant* to fail until the agent fixes them.
They are only ever run inside the isolated per-task copies made by
`run_comparison.py`, never as part of `pytest` at the repo root. Without this,
plain `pytest` would try to collect them and error on the missing code.
"""

collect_ignore = ["fixtures"]
