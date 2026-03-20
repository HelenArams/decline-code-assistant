from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def knowledge_dir(repo_root: Path) -> Path:
    return repo_root / "knowledge"


@pytest.fixture(scope="session")
def sample_csv(repo_root: Path) -> Path:
    return repo_root / "samples" / "declines.csv"
