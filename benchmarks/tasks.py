"""Benchmark task set for the LLM comparison (Member B deliverable).

Each task is a self-contained coding job on a small fixture project. The
runner copies the fixture to a fresh temp folder, runs Golu on it with one
model, then runs the task's `verify` command to decide pass/fail objectively.

The same two tasks are used for the demo video, so the comparison and the
demo stay in sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    # Fixture folder copied fresh for every run.
    fixture: Path
    # Natural-language task handed to Golu via `-p`.
    prompt: str
    # Shell command run inside the project after Golu finishes.
    # Exit code 0 == the task was completed correctly.
    verify: list[str]
    # Tools/servers the task is expected to exercise (for the report/demo notes).
    exercises: tuple[str, ...]


TASKS: list[Task] = [
    Task(
        id="bugfix",
        title="Fix failing unit tests",
        fixture=FIXTURES / "task1_bugfix",
        prompt=(
            "The tests in test_calc.py are failing. Find and fix the bugs in "
            "calc.py so that every test passes. Run the tests with pytest to "
            "confirm they pass before you finish."
        ),
        verify=["python", "-m", "pytest", "-q"],
        exercises=("filesystem: read/edit", "local: run_shell (pytest)"),
    ),
    Task(
        id="feature",
        title="Implement a function from a spec + tests",
        fixture=FIXTURES / "task2_feature",
        prompt=(
            "Implement a median(numbers) function in stats.py so that all tests "
            "in test_stats.py pass. It must handle odd- and even-length lists "
            "and must not assume the input is sorted. Run pytest to verify."
        ),
        verify=["python", "-m", "pytest", "-q"],
        exercises=("filesystem: read/write", "local: run_shell (pytest)"),
    ),
]


def get_task(task_id: str) -> Task:
    for task in TASKS:
        if task.id == task_id:
            return task
    raise KeyError(f"Unknown task id: {task_id}. Known: {[t.id for t in TASKS]}")
