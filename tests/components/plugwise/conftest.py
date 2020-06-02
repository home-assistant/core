"""Tests for the tado integration."""

import os
import pickle
import re

from Plugwise_Smile.Smile import Smile
import pytest

from tests.async_mock import AsyncMock, patch
from tests.test_util.aiohttp import AiohttpClientMocker

global ENVIRONMENT


def _read_pickle(environment, call):
    """Uncompress the pickle data."""
    fixture = call + ".pickle"
    path = os.path.join(
        os.path.dirname(__file__), "../../fixtures/plugwise/" + environment, fixture
    )
    with open(path, "rb") as fixture_file:
        return pickle.load(fixture_file)


@pytest.fixture(name="mock_smile")
def mock_smile():
    """Create a Mock Smile for testing exceptions."""
    with patch("homeassistant.components.plugwise.config_flow.Smile",) as smile_mock:
        smile_mock.InvalidAuthentication = Smile.InvalidAuthentication
        smile_mock.ConnectionFailedError = Smile.ConnectionFailedError
        smile_mock.return_value.connect.return_value = True
        yield smile_mock.return_value


@pytest.fixture(name="mock_smile_unauth")
def mock_smile_unauth(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the Plugwise Smile connection for Home Assistant."""
    aioclient_mock.get(re.compile(".*"), status=401)
    aioclient_mock.put(re.compile(".*"), status=401)


@pytest.fixture(name="mock_smile_error")
def mock_smile_error(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the Plugwise Smile connection for Home Assistant."""
    aioclient_mock.get(re.compile(".*"), status=500)
    aioclient_mock.put(re.compile(".*"), status=500)


def _get_device_data(device_id):
    """Mock return data for specific devices."""
    global ENVIRONMENT
    return _read_pickle(ENVIRONMENT, "get_device_data/" + device_id)


@pytest.fixture(name="mock_smile_adam")
def mock_smile_adam():
    """Create a Mock Adam environment for testing exceptions."""
    global ENVIRONMENT
    ENVIRONMENT = "adam_multiple_devices_per_zone"
    with patch("homeassistant.components.plugwise.Smile") as smile_mock:
        smile_mock.InvalidAuthentication = Smile.InvalidAuthentication
        smile_mock.ConnectionFailedError = Smile.ConnectionFailedError

        smile_mock.return_value.gateway_id = "fe799307f1624099878210aa0b9f1475"
        smile_mock.return_value.heater_id = "90986d591dcd426cae3ec3e8111ff730"
        smile_mock.return_value.smile_version = "3.0.15"

        smile_mock.return_value.connect.side_effect = AsyncMock(return_value=True)
        smile_mock.return_value.full_update_device.side_effect = AsyncMock(
            return_value=True
        )
        smile_mock.return_value.set_schedule_state.side_effect = AsyncMock(
            return_value=True
        )
        smile_mock.return_value.set_preset.side_effect = AsyncMock(return_value=True)
        smile_mock.return_value.set_temperature.side_effect = AsyncMock(
            return_value=True
        )
        smile_mock.return_value.set_relay_state.side_effect = AsyncMock(
            return_value=True
        )

        smile_mock.return_value.get_all_devices.return_value = _read_pickle(
            ENVIRONMENT, "get_all_devices"
        )
        smile_mock.return_value.get_device_data.side_effect = _get_device_data

        yield smile_mock.return_value


@pytest.fixture(name="mock_smile_anna")
def mock_smile_anna():
    """Create a Mock Anna environment for testing exceptions."""
    global ENVIRONMENT
    ENVIRONMENT = "anna_heatpump"
    with patch("homeassistant.components.plugwise.Smile") as smile_mock:
        smile_mock.InvalidAuthentication = Smile.InvalidAuthentication
        smile_mock.ConnectionFailedError = Smile.ConnectionFailedError

        smile_mock.return_value.gateway_id = "015ae9ea3f964e668e490fa39da3870b"
        smile_mock.return_value.heater_id = "1cbf783bb11e4a7c8a6843dee3a86927"
        smile_mock.return_value.smile_version = "4.0.15"

        smile_mock.return_value.connect.side_effect = AsyncMock(return_value=True)
        smile_mock.return_value.full_update_device.side_effect = AsyncMock(
            return_value=True
        )
        smile_mock.return_value.set_schedule_state.side_effect = AsyncMock(
            return_value=True
        )
        smile_mock.return_value.set_preset.side_effect = AsyncMock(return_value=True)
        smile_mock.return_value.set_temperature.side_effect = AsyncMock(
            return_value=True
        )
        smile_mock.return_value.set_relay_state.side_effect = AsyncMock(
            return_value=True
        )

        smile_mock.return_value.get_all_devices.return_value = _read_pickle(
            ENVIRONMENT, "get_all_devices"
        )
        smile_mock.return_value.get_device_data.side_effect = _get_device_data

        yield smile_mock.return_value


@pytest.fixture(name="mock_smile_p1")
def mock_smile_p1():
    """Create a Mock P1 DSMR environment for testing exceptions."""
    global ENVIRONMENT
    ENVIRONMENT = "p1v3_full_option"
    with patch("homeassistant.components.plugwise.Smile") as smile_mock:
        smile_mock.InvalidAuthentication = Smile.InvalidAuthentication
        smile_mock.ConnectionFailedError = Smile.ConnectionFailedError

        smile_mock.return_value.gateway_id = "e950c7d5e1ee407a858e2a8b5016c8b3"
        smile_mock.return_value.heater_id = None
        smile_mock.return_value.smile_version = "3.3.9"

        smile_mock.return_value.connect.side_effect = AsyncMock(return_value=True)
        smile_mock.return_value.full_update_device.side_effect = AsyncMock(
            return_value=True
        )

        smile_mock.return_value.get_all_devices.return_value = _read_pickle(
            ENVIRONMENT, "get_all_devices"
        )
        smile_mock.return_value.get_device_data.side_effect = _get_device_data

        yield smile_mock.return_value
