"""Tests for the HDMI-CEC component."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def MockCecAdapter():
    """Mock CecAdapter.

    Always mocked as it import the `cec` library which is part of `libcec`.
    """
    with patch(
        "homeassistant.components.hdmi_cec.CecAdapter", autospec=True
    ) as MockCecAdapter:
        yield MockCecAdapter


@pytest.fixture
def MockHDMINetwork():
    """Mock HDMINetwork."""
    with patch(
        "homeassistant.components.hdmi_cec.HDMINetwork", autospec=True
    ) as MockHDMINetwork:
        yield MockHDMINetwork
