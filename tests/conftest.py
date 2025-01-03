from pathlib import Path

import pytest

FIXTURES_PATH = (Path(__file__).parent / "fixtures").absolute()


@pytest.fixture(scope="module")
def fixtures_path():
    return FIXTURES_PATH
