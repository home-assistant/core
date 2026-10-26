"""Tests for the setup of the Voltie Charger integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from voltie import VoltieAuthenticationError, VoltieConnectionError, VoltieError

from homeassistant.components.voltie_charger.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import CHARGER_ID, status_fixture


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_voltie: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("method", "side_effect", "state"),
    [
        ("status", VoltieConnectionError, ConfigEntryState.SETUP_RETRY),
        ("status", VoltieError, ConfigEntryState.SETUP_RETRY),
        ("status", VoltieAuthenticationError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_voltie: MagicMock,
    method: str,
    side_effect: type[Exception] | Exception,
    state: ConfigEntryState,
) -> None:
    """Test the entry is retried, or needs the user, when setup fails."""
    getattr(mock_voltie, method).side_effect = side_effect
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state


async def test_setup_wrong_charger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_voltie: MagicMock,
) -> None:
    """Test another charger answering at the address is not taken over."""
    mock_voltie.status.return_value = status_fixture(charger_id="0000000011111111")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == (
        "A different Voltie charger answers at 192.168.1.234. Remove this charger"
        " and add it again with its current address"
    )


@pytest.mark.usefixtures("init_integration")
async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the charger is registered as a device."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CHARGER_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Voltie"
    assert device.name == "Voltie Charger 4335"
    assert device.serial_number == CHARGER_ID
    assert device.sw_version == "1.3.25"
    assert device.configuration_url == "http://192.168.1.234:5059"


@pytest.mark.usefixtures("init_integration")
async def test_unavailable_and_recovery(
    hass: HomeAssistant,
    mock_voltie: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable when the charger cannot be reached."""
    entity_id = "sensor.voltie_charger_4335_charging_power"
    assert hass.states.get(entity_id).state == "10.95"

    mock_voltie.status.side_effect = VoltieConnectionError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_voltie.status.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "10.95"


@pytest.mark.usefixtures("mock_voltie")
@pytest.mark.parametrize("api_version", [4, None])
async def test_older_firmware(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test firmware with an HTTP API older than version 5 is refused."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "unsupported_firmware"
