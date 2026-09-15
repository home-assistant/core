"""Setup, unload, and device-removal behavior."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from pycoolbot import CoolbotAuthError, CoolbotError

from homeassistant.components.coolbot.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import make_device

from tests.common import MockConfigEntry, async_fire_time_changed


async def _tick(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + UPDATE_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads, exposes runtime data, and closes its socket on unload."""
    assert await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.async_close.assert_awaited()


async def test_setup_retries_when_service_is_unreachable(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A connection failure at setup schedules a retry, not a hard error.

    The failed client is closed rather than leaked: a rejected connect still
    leaves its socket and reader task running until someone closes it.
    """
    mock_client.async_connect.side_effect = CoolbotError("down")

    assert not await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.async_close.assert_awaited()


async def test_an_aborted_first_refresh_closes_the_socket(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """When setup fails after connecting, nothing else can close the socket.

    An unexpected error is the case that matters: the library's own errors are
    already closed by the refresh itself, but runtime_data is never assigned,
    so an unhandled one would otherwise leave the connection open for good.
    """
    mock_client.async_get_devices.side_effect = RuntimeError("surprise")

    assert not await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.async_close.assert_awaited()


async def test_setup_succeeds_for_an_account_with_no_devices(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """An account reporting no coolers loads rather than retrying forever."""
    mock_client.async_get_devices.return_value = []

    assert await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.data == {}


async def test_setup_fails_as_an_auth_error_on_bad_credentials(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Rejected credentials fail setup as an auth error instead of retrying.

    ConfigEntryAuthFailed marks the entry SETUP_ERROR rather than scheduling
    retries; the reauth flow that would let the user fix the password in place
    arrives in a follow-up PR.
    """
    mock_client.async_connect.side_effect = CoolbotAuthError("rejected")

    assert not await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_hardware_details_that_replay_late_reach_the_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Model and firmware pins can replay after the cooler is created.

    Connecting waits for the pins that identify a cooler, not for all of them,
    and device info is only read when an entity is added, so these details
    would otherwise stay missing until the entry is reloaded.
    """
    mock_client.async_get_devices.return_value = [
        make_device(coolbot_hardware=None, jumper_firmware=None)
    ]
    assert await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "coolbot_aabbccddeeff"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model == "CoolBot Pro"
    assert device.sw_version is None

    mock_client.async_get_devices.return_value = [make_device()]
    await _tick(hass)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "coolbot_aabbccddeeff"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model == "CoolBot Pro 6"
    assert device.sw_version == "1.2.3"


async def test_a_rename_in_the_account_reaches_the_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A cooler renamed in the CoolBot account is renamed here too.

    Device info is only read when an entity is added, so without the refresh
    writing the name to the registry the old name would stick until the entry
    is reloaded.
    """
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = [make_device(name="Flower cooler")]
    await _tick(hass)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "coolbot_aabbccddeeff"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Flower cooler"
