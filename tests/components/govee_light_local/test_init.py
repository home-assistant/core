"""Tests init for the Govee Local API integration."""

from unittest.mock import AsyncMock, MagicMock

from govee_local_api import GoveeDevice

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import (
    CONF_AUTO_DISCOVERY,
    CONF_IPS_TO_REMOVE,
    CONF_MANUAL_DEVICES,
    DOMAIN,
    SIGNAL_GOVEE_DEVICE_REMOVE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .conftest import DEFAULT_CAPABILITIES, set_mocked_devices

from tests.common import MockConfigEntry


async def test_update_options_remove_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test update options triggers reload."""

    manual_device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="asdawdqwdqwd",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device.is_manual = True
    set_mocked_devices(
        mock_govee_api,
        [manual_device],
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: False},
        options={},
    )

    config_entry.add_to_hass(hass)
    remove_signal = MagicMock()
    async_dispatcher_connect(hass, SIGNAL_GOVEE_DEVICE_REMOVE, remove_signal)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_IPS_TO_REMOVE: ["192.168.1.100"]}
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    remove_signal.assert_called_once_with("asdawdqwdqwd")


async def test_update_options_enable_discovery(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test update options triggers reload."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: False},
        options={},
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_AUTO_DISCOVERY: True}
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    mock_govee_api.set_discovery_enabled.assert_called_once_with(True)


async def test_update_options_add_devices(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding multiple devices via options."""
    # Create two manual devices that will be returned when add_manual_device is called
    device1 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="device1-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    device1.is_manual = True

    device2 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.101",
        fingerprint="device2-fingerprint",
        sku="H6199",
        capabilities=DEFAULT_CAPABILITIES,
    )
    device2.is_manual = True

    # Empty initial devices list
    set_mocked_devices(mock_govee_api, [])

    # Create entry with no manual devices
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: False},
        options={},
    )

    config_entry.add_to_hass(hass)

    # Setup initial integration
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Update options to add first device
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_MANUAL_DEVICES: ["192.168.1.100"]}
    )
    await hass.async_block_till_done()

    # Verify first device is added
    mock_govee_api.add_manual_device.assert_called_once_with("192.168.1.100")
    assert len(mock_govee_api.devices) == 1
    assert mock_govee_api.devices[0].ip == "192.168.1.100"

    # Check entity is created for first device
    entity_registry = hass.helpers.entity_registry.async_get(hass)
    entity_id1 = entity_registry.async_get_entity_id(
        "light", DOMAIN, "device1-fingerprint"
    )
    assert entity_id1 == f"light.{device1.sku}"
    assert hass.states.get(entity_id1) is not None

    # Update options to add second device
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_MANUAL_DEVICES: ["192.168.1.101"]}
    )
    await hass.async_block_till_done()

    # Verify second device is added
    mock_govee_api.add_manual_device.assert_called_with("192.168.1.101")
    assert len(mock_govee_api.devices) == 2
    assert {device.ip for device in mock_govee_api.devices} == {
        "192.168.1.100",
        "192.168.1.101",
    }

    # Check entity is created for second device
    entity_id2 = entity_registry.async_get_entity_id(
        "light", DOMAIN, "device2-fingerprint"
    )
    assert entity_id2 == f"light.{device2.sku}"
    assert hass.states.get(entity_id2) is not None
