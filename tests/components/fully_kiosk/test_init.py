"""Tests for the Fully Kiosk Browser integration."""
import json
from unittest.mock import MagicMock, patch

from fullykiosk import FullyKioskError
import pytest

from homeassistant.components.fully_kiosk.const import DOMAIN
from homeassistant.components.fully_kiosk.entity import valid_global_mac_address
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, load_fixture


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fully_kiosk: MagicMock,
) -> None:
    """Test the Fully Kiosk Browser configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_fully_kiosk.getDeviceInfo.mock_calls) == 1
    assert len(mock_fully_kiosk.getSettings.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect",
    [FullyKioskError("error", "status"), TimeoutError],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fully_kiosk: MagicMock,
    side_effect: Exception,
) -> None:
    """Test the Fully Kiosk Browser configuration entry not ready."""
    mock_fully_kiosk.getDeviceInfo.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def _load_config(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_info_fixture: str,
) -> None:
    with patch(
        "homeassistant.components.fully_kiosk.coordinator.FullyKiosk",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value
        client.getDeviceInfo.return_value = json.loads(
            load_fixture(device_info_fixture, DOMAIN)
        )
        client.getSettings.return_value = json.loads(
            load_fixture("listsettings.json", DOMAIN)
        )

        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_multiple_kiosk_with_empty_mac(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that multiple kiosk devices with empty MAC don't get merged."""
    config_entry1 = MockConfigEntry(
        title="Test device 1",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "mocked-password",
            CONF_MAC: "",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
        unique_id="111111",
    )
    await _load_config(hass, config_entry1, "deviceinfo_empty_mac1.json")
    assert len(device_registry.devices) == 1

    config_entry2 = MockConfigEntry(
        title="Test device 2",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.2",
            CONF_PASSWORD: "mocked-password",
            CONF_MAC: "",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
        unique_id="22222",
    )
    await _load_config(hass, config_entry2, "deviceinfo_empty_mac2.json")
    assert len(device_registry.devices) == 2

    state1 = hass.states.get("sensor.test_kiosk_1_battery")
    assert state1

    state2 = hass.states.get("sensor.test_kiosk_2_battery")
    assert state2

    entry1 = entity_registry.async_get("sensor.test_kiosk_1_battery")
    assert entry1
    assert entry1.unique_id == "abcdef-111111-batteryLevel"

    entry2 = entity_registry.async_get("sensor.test_kiosk_2_battery")
    assert entry2
    assert entry2.unique_id == "abcdef-222222-batteryLevel"

    assert entry1.device_id != entry2.device_id

    device1 = device_registry.async_get(entry1.device_id)
    assert device1

    device2 = device_registry.async_get(entry2.device_id)
    assert device2

    assert device1 != device2


async def test_valid_global_mac_address() -> None:
    """Test valid_global_mac_address function."""
    assert valid_global_mac_address("a1:bb:cc:dd:ee:ff")
    assert not valid_global_mac_address("02:00:00:00:00:00")
    assert not valid_global_mac_address(None)
    assert not valid_global_mac_address("foobar")
