"""Fixturess for SQL tests."""
import os

import pytest

from tests.common import get_test_config_dir


@pytest.fixture(autouse=True)
def remove_file():
    """Remove db."""
    yield
    file = os.path.join(get_test_config_dir(), "home-assistant_v2.db")
    if os.path.isfile(file):
        os.remove(file)
