"""Common tradfri test fixtures."""
from unittest.mock import Mock, PropertyMock, patch

import pytest

from . import GATEWAY_ID, TRADFRI_PATH

# pylint: disable=protected-access


@pytest.fixture
def mock_gateway_info():
    """Mock get_gateway_info."""
    with patch(f"{TRADFRI_PATH}.config_flow.get_gateway_info") as gateway_info:
        yield gateway_info


@pytest.fixture
def mock_entry_setup():
    """Mock entry setup."""
    with patch(f"{TRADFRI_PATH}.async_setup_entry") as mock_setup:
        mock_setup.return_value = True
        yield mock_setup


@pytest.fixture(name="mock_gateway")
def mock_gateway_fixture():
    """Mock a Tradfri gateway."""

    def get_devices():
        """Return mock devices."""
        return gateway.mock_devices

    def get_groups():
        """Return mock groups."""
        return gateway.mock_groups

    gateway_info = Mock(id=GATEWAY_ID, firmware_version="1.2.1234")

    def get_gateway_info():
        """Return mock gateway info."""
        return gateway_info

    gateway = Mock(
        get_devices=get_devices,
        get_groups=get_groups,
        get_gateway_info=get_gateway_info,
        mock_devices=[],
        mock_groups=[],
        mock_responses=[],
    )
    with patch(f"{TRADFRI_PATH}.Gateway", return_value=gateway), patch(
        f"{TRADFRI_PATH}.config_flow.Gateway", return_value=gateway
    ):
        yield gateway


@pytest.fixture(name="mock_api")
def mock_api_fixture(mock_gateway):
    """Mock api."""

    async def api(command, timeout=None):
        """Mock api function."""
        # Store the data for "real" command objects.
        if hasattr(command, "_data") and not isinstance(command, Mock):
            mock_gateway.mock_responses.append(command._data)
        return command

    return api


@pytest.fixture
def mock_api_factory(mock_api):
    """Mock pytradfri api factory."""
    with patch(f"{TRADFRI_PATH}.APIFactory", autospec=True) as factory:
        factory.init.return_value = factory.return_value
        factory.return_value.request = mock_api
        yield factory.return_value


@pytest.fixture(autouse=True)
def setup(request):
    """
    Set up patches for pytradfri methods for the fan platform.

    This is used in test_fan as well as in test_sensor.
    """
    with patch(
        "pytradfri.device.AirPurifierControl.raw",
        new_callable=PropertyMock,
        return_value=[{"mock": "mock"}],
    ), patch(
        "pytradfri.device.AirPurifierControl.air_purifiers",
    ):
        yield
