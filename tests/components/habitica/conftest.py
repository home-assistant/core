"""Tests for the habitica component."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def disable_plumbum():
    """Disable plumbum in tests as it can cause the test suite to fail.

    plumbum can leave behind PlumbumTimeoutThreads
    """
    with patch("plumbum.local"), patch("plumbum.colors"):
        yield
