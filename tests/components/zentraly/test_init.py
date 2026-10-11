"""Tests for Zentraly setup and device metadata through Home Assistant."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zentraly import (
    ZentralyAuthenticationError,
    ZentralyConnectionError,
    ZentralyDeviceInfo,
)

from homeassistant.components.zentraly.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_TEMPERATURE, CONF_DEVICE_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import DEVICE_ID, ENTITY_ID, MAC

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("mock_api", "mock_climate_api", "mock_device_info")


@pytest.mark.parametrize(
    ("error", "expected", "key"),
    [
        pytest.param(
            ZentralyAuthenticationError,
            ConfigEntryState.SETUP_ERROR,
            "authentication_failed",
            id="authentication",
        ),
        pytest.param(
            ZentralyConnectionError,
            ConfigEntryState.SETUP_RETRY,
            "setup_cannot_connect",
            id="connection",
        ),
    ],
)
async def test_translated_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    error: type[Exception],
    expected: ConfigEntryState,
    key: str,
) -> None:
    """Setup failures expose translated errors through the config entry."""
    mock_api.async_validate_password.side_effect = error
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is expected
    assert mock_config_entry.error_reason_translation_key == key
    assert mock_config_entry.error_reason_translation_placeholders == {
        "device_id": DEVICE_ID
    }


async def test_translated_unsupported_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An unsupported stored model fails setup with a translated explanation."""
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_DEVICE_ID: "UNKNOWN"}
    )
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "unsupported_model"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "device_id": "UNKNOWN"
    }


@pytest.mark.usefixtures("setup_integration")
async def test_setup_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Load one climate entity and register the physical thermostat."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(hass.states.async_all()) == 1
    assert hass.states.get(ENTITY_ID).state == "heat"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Zentraly"
    assert device.model == "Termostato Inalámbrico Wi-Fi"
    assert device.model_id == "ZTTIN"
    assert device.name == DEVICE_ID
    assert device.serial_number == DEVICE_ID
    assert (dr.CONNECTION_NETWORK_MAC, dr.format_mac(MAC)) in device.connections
    mock_api.async_connect.assert_awaited_once_with()


async def test_setup_unexpected_mac(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Setup retries instead of connecting to a different device."""
    mock_api.async_validate_password.return_value = "001122334455"
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "unexpected_device"
    mock_api.async_connect.assert_not_awaited()


@pytest.mark.usefixtures("setup_integration")
async def test_device_info_periodic_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Metadata refreshes daily, independently of state polling, and stops on unload."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert device.sw_version == "1.0"
    assert device.hw_version == "2.0"
    mock_device_info.assert_awaited_once_with()
    mock_device_info.reset_mock()
    mock_device_info.return_value = ZentralyDeviceInfo(hardware_version="2.1")
    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(minutes=5))
    await hass.async_block_till_done()
    mock_device_info.assert_not_awaited()
    async_fire_time_changed(hass, now + timedelta(hours=24))
    await hass.async_block_till_done()
    mock_device_info.assert_awaited_once_with()
    assert device_registry.async_get(device.id).sw_version == "1.0"
    assert device_registry.async_get(device.id).hw_version == "2.1"
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    async_fire_time_changed(hass, now + timedelta(hours=48))
    await hass.async_block_till_done()
    mock_device_info.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("info", "firmware", "hardware"),
    [
        pytest.param(
            ZentralyDeviceInfo(firmware_version="1.1"), "1.1", "2.0", id="firmware-only"
        ),
        pytest.param(
            ZentralyDeviceInfo(hardware_version="2.1"), "1.0", "2.1", id="hardware-only"
        ),
        pytest.param(ZentralyDeviceInfo(), "1.0", "2.0", id="no-readings"),
        pytest.param(ZentralyConnectionError(), "1.0", "2.0", id="read-error"),
    ],
)
async def test_partial_device_info_after_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: AsyncMock,
    device_registry: dr.DeviceRegistry,
    info: ZentralyDeviceInfo | ZentralyConnectionError,
    firmware: str,
    hardware: str,
) -> None:
    """A fresh setup preserves stored versions absent from the first reading."""
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, DEVICE_ID)},
        sw_version="1.0",
        hw_version="2.0",
    )
    mock_device_info.side_effect = [info]
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    updated = device_registry.async_get(device.id)
    assert updated.sw_version == firmware
    assert updated.hw_version == hardware


@pytest.mark.parametrize(
    "initial_read",
    [
        pytest.param(19.0, id="success"),
        pytest.param(ZentralyConnectionError(), id="connection-error"),
    ],
)
async def test_climate_periodic_refresh_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_climate_api: MagicMock,
    initial_read: float | ZentralyConnectionError,
) -> None:
    """Even after an initial read failure the entity registers and retries on schedule."""
    mock_climate_api.async_get_current_temperature.side_effect = [initial_read, 19.0]
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(hass.states.async_all("climate")) == 1
    mock_climate_api.async_get_current_temperature.reset_mock()
    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(minutes=4))
    await hass.async_block_till_done()
    mock_climate_api.async_get_current_temperature.assert_not_awaited()
    async_fire_time_changed(hass, now + timedelta(minutes=5))
    await hass.async_block_till_done()
    mock_climate_api.async_get_current_temperature.assert_awaited_once_with()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 21.0
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    async_fire_time_changed(hass, now + timedelta(minutes=10))
    await hass.async_block_till_done()
    mock_climate_api.async_get_current_temperature.assert_awaited_once_with()


async def test_setup_failure_disconnects(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """A platform setup failure still releases the library connection."""
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=ConfigEntryError("Platform setup failed"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_api.async_disconnect.assert_awaited_once_with()


async def test_device_info_connection_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    mock_device_info: AsyncMock,
    connection_state: Callable[[bool], None],
) -> None:
    """Connection events deduplicate pending metadata reads; unloading cancels them."""
    mock_api.connected = False
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def read() -> ZentralyDeviceInfo:
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
        return ZentralyDeviceInfo()

    mock_device_info.side_effect = read
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_device_info.assert_not_awaited()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    connection_state(False)
    mock_device_info.assert_not_awaited()
    connection_state(True)
    await started.wait()
    connection_state(True)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=24))
    await hass.async_block_till_done()
    mock_device_info.assert_awaited_once_with()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert cancelled.is_set()
    assert mock_api.add_connection_state_listener.return_value.call_count == 2
