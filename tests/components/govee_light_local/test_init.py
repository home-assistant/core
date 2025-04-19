"""Tests init for the Govee Local API integration."""

from unittest.mock import AsyncMock, MagicMock

from govee_local_api import GoveeDevice

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import (
    CONF_AUTO_DISCOVERY,
    CONF_IPS_TO_REMOVE,
    CONF_MANUAL_DEVICES,
    CONF_OPTION_MODE,
    DOMAIN,
    SIGNAL_GOVEE_DEVICE_REMOVE,
    OptionMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .conftest import DEFAULT_CAPABILITIES, set_mocked_devices

from tests.common import MockConfigEntry


async def test_setup_entry_with_options(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test update options triggers reload."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: False},
        options={CONF_MANUAL_DEVICES: ["192.168.1.100"]},
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_govee_api.add_device_to_discovery_queue.assert_called_once_with(
        "192.168.1.100"
    )


async def test_update_options_remove_device_discovered(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test update options triggers reload."""

    manual_device1 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="manual_device1-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device1.is_manual = True
    manual_device2 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.101",
        fingerprint="manual_device2-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device2.is_manual = True
    set_mocked_devices(
        mock_govee_api,
        [manual_device1, manual_device2],
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

    entity_registry = er.async_get(hass)
    assert entity_registry.async_get("light.h615a") is not None
    assert entity_registry.async_get("light.h615b") is not None

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_OPTION_MODE: OptionMode.REMOVE_DEVICE,
            CONF_MANUAL_DEVICES: {"192.168.1.100", "192.168.1.101"},
            CONF_IPS_TO_REMOVE: {f"{manual_device1.ip}"},
        },
    )
    set_mocked_devices(mock_govee_api, [manual_device2])
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    remove_signal.assert_called_once_with(f"{manual_device1.fingerprint}")
    mock_govee_api.remove_device_from_discovery_queue.assert_called_once_with(
        manual_device1.ip
    )

    assert config_entry.options == {
        CONF_IPS_TO_REMOVE: set(),
        CONF_MANUAL_DEVICES: {f"{manual_device2.ip}"},
        CONF_OPTION_MODE: OptionMode.REMOVE_DEVICE,
    }

    assert entity_registry.async_get("light.h615b") is not None
    assert entity_registry.async_get("light.h615a") is None


async def test_update_options_remove_device_in_queue(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test update options triggers reload."""

    manual_device1 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="manual_device1-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device1.is_manual = True

    set_mocked_devices(
        mock_govee_api,
        [manual_device1],
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
        config_entry,
        options={
            CONF_OPTION_MODE: OptionMode.ADD_DEVICE,
            CONF_MANUAL_DEVICES: {"192.168.1.101"},
        },
    )
    await hass.async_block_till_done()

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_OPTION_MODE: OptionMode.REMOVE_DEVICE,
            CONF_MANUAL_DEVICES: {"192.168.1.101"},
            CONF_IPS_TO_REMOVE: {"192.168.1.101"},
        },
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    remove_signal.assert_not_called()

    assert config_entry.options == {
        CONF_IPS_TO_REMOVE: set(),
        CONF_MANUAL_DEVICES: set(),
        CONF_OPTION_MODE: OptionMode.REMOVE_DEVICE,
    }

    assert len(hass.states.async_all()) == 1


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
        config_entry,
        options={
            CONF_OPTION_MODE: OptionMode.CONFIGURE_AUTO_DISCOVERY,
            CONF_AUTO_DISCOVERY: True,
        },
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    mock_govee_api.set_discovery_enabled.assert_called_once_with(True)


async def test_update_options_add_devices(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding multiple devices via options."""

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

    set_mocked_devices(mock_govee_api, [])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: False},
        options={},
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    set_mocked_devices(mock_govee_api, [device1])
    mock_govee_api.get_device_by_ip.side_effect = [None, device1]

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_OPTION_MODE: OptionMode.ADD_DEVICE,
            CONF_MANUAL_DEVICES: [device1.ip],
        },
    )

    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    mock_govee_api.add_device_to_discovery_queue.assert_called_once_with(device1.ip)
