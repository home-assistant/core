"""Fixtures for vaillant tests."""

from unittest import mock

import pytest

from tests.components.vaillant import SystemManagerMock


@pytest.fixture(name="mock_system_manager")
def fixture_mock_system_manager():
    """Mock the vaillant system manager."""
    with mock.patch("pymultimatic.systemmanager.SystemManager", new=SystemManagerMock):
        yield
    SystemManagerMock.reset_mock()
