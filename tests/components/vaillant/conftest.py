"""Fixtures for vaillant tests."""

import mock
import pytest

from tests.common import MockDependency
from tests.components.vaillant import SystemManagerMock


@pytest.fixture(name="mock_vaillant", scope='session')
def fixture_mock_vaillant():
    """Mock vaillant dependency."""
    with MockDependency('vr900-connector'):
        yield


@pytest.fixture(name="mock_system_manager")
def fixture_mock_system_manager(mock_vaillant):
    """Mock the vaillant system manager."""
    with mock.patch('vr900connector.systemmanager.SystemManager',
                    new=SystemManagerMock):
        yield
    SystemManagerMock.reset()
