"""Tests helpers."""

import pytest


@pytest.fixture
def config_1() -> dict[str, str | int]:
    """Awattar configuration."""
    return {"country": "de", "scan_interval": 10}


@pytest.fixture
def config_2() -> dict[str, str | int]:
    """Awattar configuration."""
    return {"country": "at", "scan_interval": 20}


@pytest.fixture
def config_interval_min() -> dict[str, str | int]:
    """Wrong Awattar configuration."""
    return {"country": "de", "scan_interval": -10}


@pytest.fixture
def config_interval_max() -> dict[str, str | int]:
    """Wrong Awattar configuration."""
    return {"country": "de", "scan_interval": 60001}
