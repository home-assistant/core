"""Tests for the Govee Local API integration."""

from unittest.mock import AsyncMock, MagicMock

from govee_local_api import GoveeDevice

from homeassistant.components.govee_light_local.const import (
    CONF_AUTO_DISCOVERY,
    CONF_IPS_TO_REMOVE,
    DOMAIN,
    SIGNAL_GOVEE_DEVICE_REMOVE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .conftest import DEFAULT_CAPABILITIES, set_mocked_devices

from tests.common import MockConfigEntry


async def test_update_options(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
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
    assert config_entry.state is ConfigEntryState.LOADED

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_IPS_TO_REMOVE: ["192.168.1.100"]}
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED
    remove_signal.assert_called_once_with("asdawdqwdqwd")
