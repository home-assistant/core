"""Fixtures for nuki tests."""

from collections.abc import Generator

import pytest
import requests_mock


@pytest.fixture
def mock_nuki_requests() -> Generator[requests_mock.Mocker]:
    """Mock nuki HTTP requests."""
    with requests_mock.Mocker() as mock:
        yield mock
