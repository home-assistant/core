"""Tests for the Tado X (hops.tado.com) compatibility path."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from PyTado.exceptions import TadoNotSupportedException
from PyTado.http import DeviceActivationStatus
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

from homeassistant.components.tado import DOMAIN
from homeassistant.components.tado.coordinator import TadoDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_tadox_api() -> Generator[MagicMock]:
    """Mock a Tado X client (hops.tado.com API shapes)."""
    with (
        patch("homeassistant.components.tado.Tado") as mock_tado,
        patch("homeassistant.components.tado.config_flow.Tado", new=mock_tado),
    ):
        client = mock_tado.return_value
        client.device_verification_url.return_value = (
            "https://login.tado.com/oauth2/device?user_code=TEST"
        )
        client.device_activation_status.return_value = DeviceActivationStatus.COMPLETED
        client._http.is_x_line = True
        client.get_me.return_value = load_json_object_fixture("me.json", DOMAIN)
        client.get_zones.return_value = load_json_array_fixture(
            "tadox_zones.json", DOMAIN
        )
        client.get_devices.return_value = load_json_array_fixture(
            "tadox_devices.json", DOMAIN
        )
        client.get_zone_states.return_value = load_json_array_fixture(
            "tadox_zone_states.json", DOMAIN
        )
        client.get_zone_overlay_default.side_effect = TadoNotSupportedException(
            "Not supported on Tado X"
        )
        client.get_heating_circuits.return_value = []
        client.get_zone_control.return_value = {}
        client.get_weather.return_value = load_json_object_fixture(
            "weather.json", DOMAIN
        )
        client.get_home_state.return_value = load_json_object_fixture(
            "home_state.json", DOMAIN
        )
        client.get_refresh_token.return_value = "refresh"
        client.rate_limit_info.return_value = {
            "limit": "1000",
            "remaining": "999",
        }
        yield client


async def test_tadox_setup_entry(
    hass: HomeAssistant,
    mock_tadox_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a Tado X system sets up and exposes climate entities."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("climate.room_1_room_1")
    assert state is not None
    assert state.attributes["current_temperature"] == 24.0
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    state = hass.states.get("climate.room_2_room_2")
    assert state is not None
    assert state.attributes["current_temperature"] == 18.0
    assert state.attributes[ATTR_TEMPERATURE] == 20.0


def test_normalize_devices_flattens_nested_lists() -> None:
    """Test nested device lists are flattened and X API keys are backfilled."""
    raw_devices = [
        [
            {
                "serialNumber": "IB1234567890",
                "type": "IB02",
                "firmwareVersion": "245.1",
                "connection": {"state": "CONNECTED"},
            }
        ],
        {
            "serialNumber": "VA1234567890",
            "type": "VA04",
            "firmwareVersion": "243.1",
            "temperatureOffset": 0.5,
            "connection": {"state": "CONNECTED"},
        },
    ]

    devices = TadoDataUpdateCoordinator._normalize_devices(raw_devices)

    assert len(devices) == 2

    bridge = devices[0]
    assert bridge["shortSerialNo"] == "IB1234567890"
    assert bridge["serialNo"] == "IB1234567890"
    assert bridge["deviceType"] == "IB02"
    assert bridge["currentFwVersion"] == "245.1"

    valve = devices[1]
    assert valve["shortSerialNo"] == "VA1234567890"
    assert valve["deviceType"] == "VA04"
    assert valve["temperatureOffset"] == {"celsius": 0.5, "fahrenheit": 0.9}


def test_normalize_devices_keeps_classic_keys() -> None:
    """Test devices already using the classic API keys are left untouched."""
    raw_devices = [
        {
            "shortSerialNo": "WR1",
            "serialNo": "WR1",
            "deviceType": "WR01",
            "currentFwVersion": "54.2",
            "temperatureOffset": {"celsius": -1.0, "fahrenheit": -1.8},
        }
    ]

    devices = TadoDataUpdateCoordinator._normalize_devices(raw_devices)

    assert devices[0] == raw_devices[0]
