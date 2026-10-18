"""Tests for Broadlink devices."""

import asyncio
from datetime import timedelta
from unittest.mock import call, patch

import broadlink_async.exceptions as blke
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.broadlink.const import (
    BROADLINK_DATA,
    CONF_AUTO_SYNC_TIME,
    DOMAIN,
)
from homeassistant.components.broadlink.device import get_domains
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_FRIENDLY_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_device

DEVICE_FACTORY = "homeassistant.components.broadlink.device.blk.gendevice"


async def test_device_setup(hass: HomeAssistant) -> None:
    """Test a successful setup."""
    device = get_device("Office")

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        mock_setup = await device.setup_entry(hass)

    assert mock_setup.entry.state is ConfigEntryState.LOADED
    assert mock_setup.api.auth.call_count == 1
    assert mock_setup.api.get_fwversion.call_count == 1
    assert mock_setup.api.aclose.await_count == 0
    assert mock_setup.factory.call_count == 1

    forward_entries = set(mock_forward.mock_calls[0][1][1])
    domains = get_domains(mock_setup.api.type)
    assert mock_forward.call_count == 1
    assert forward_entries == domains
    assert mock_init.call_count == 0


async def test_device_setup_rm5plus(hass: HomeAssistant) -> None:
    """Test an RM5 Plus sets up with the IR remote platforms and no sensors."""
    device = get_device("Study")

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        mock_setup = await device.setup_entry(hass)

    assert mock_setup.entry.state is ConfigEntryState.LOADED
    assert set(mock_forward.mock_calls[0][1][1]) == {
        Platform.INFRARED,
        Platform.REMOTE,
        Platform.SWITCH,
    }


async def test_device_setup_authentication_error(hass: HomeAssistant) -> None:
    """Test we handle an authentication error."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_setup.entry.reason == "Failed to set up the device at 192.168.0.12"
    assert mock_setup.api.auth.call_count == 1
    assert mock_setup.api.aclose.await_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 1
    assert mock_init.mock_calls[0][2]["context"]["source"] == "reauth"
    assert mock_init.mock_calls[0][2]["data"] == device.get_entry_data()


async def test_device_setup_network_timeout(hass: HomeAssistant) -> None:
    """Test we handle a network timeout."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.NetworkTimeoutError()

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        mock_setup.entry.reason == "Failed to connect to the device at 192.168.0.13: "
    )
    assert mock_setup.api.auth.call_count == 1
    assert mock_setup.api.aclose.await_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_setup_os_error(hass: HomeAssistant) -> None:
    """Test we handle an OS error."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = OSError()

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        mock_setup.entry.reason == "Failed to connect to the device at 192.168.0.13: "
    )
    assert mock_setup.api.auth.call_count == 1
    assert mock_setup.api.aclose.await_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_setup_broadlink_exception(hass: HomeAssistant) -> None:
    """Test we handle a Broadlink exception."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.BroadlinkException()

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_setup.entry.reason == "Failed to set up the device at 192.168.0.13"
    assert mock_setup.api.auth.call_count == 1
    assert mock_setup.api.aclose.await_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_setup_update_network_timeout(hass: HomeAssistant) -> None:
    """Test we handle a network timeout in the update step."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = blke.NetworkTimeoutError()

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_setup.api.auth.call_count == 1
    assert mock_setup.api.aclose.await_count == 1
    assert mock_setup.api.check_sensors.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_request_endpoint_closed(hass: HomeAssistant) -> None:
    """Test a request on a closed endpoint is raised without a retry."""
    device = get_device("Office")
    mock_api = device.get_mock_api()

    with patch.object(hass.config_entries, "async_forward_entry_setups"):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    mock_api.check_sensors.side_effect = blke.EndpointClosedError()
    mock_api.auth.reset_mock()
    mock_api.check_sensors.reset_mock()

    broadlink_device = hass.data[BROADLINK_DATA].devices[mock_setup.entry.entry_id]
    with pytest.raises(blke.EndpointClosedError):
        await broadlink_device.async_request(mock_api.check_sensors)

    assert mock_api.check_sensors.call_count == 1
    assert mock_api.auth.call_count == 0


async def test_device_setup_update_authorization_error(hass: HomeAssistant) -> None:
    """Test we handle an authorization error in the update step."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = (
        blke.AuthorizationError(),
        {"temperature": 30},
    )

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.LOADED
    assert mock_setup.api.auth.call_count == 2
    assert mock_setup.api.check_sensors.call_count == 2

    forward_entries = set(mock_forward.mock_calls[0][1][1])
    domains = get_domains(mock_api.type)
    assert mock_forward.call_count == 1
    assert forward_entries == domains
    assert mock_init.call_count == 0


async def test_device_setup_update_authentication_error(hass: HomeAssistant) -> None:
    """Test we handle an authentication error in the update step."""
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = blke.AuthorizationError()
    mock_api.auth.side_effect = (None, blke.AuthenticationError())

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_setup.api.auth.call_count == 2
    assert mock_setup.api.aclose.await_count == 1
    assert mock_setup.api.check_sensors.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 1
    assert mock_init.mock_calls[0][2]["context"]["source"] == "reauth"
    assert mock_init.mock_calls[0][2]["data"] == device.get_entry_data()


async def test_device_setup_update_broadlink_exception(hass: HomeAssistant) -> None:
    """Test we handle a Broadlink exception in the update step."""
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = blke.BroadlinkException()

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_setup.api.auth.call_count == 1
    assert mock_setup.api.aclose.await_count == 1
    assert mock_setup.api.check_sensors.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_setup_get_fwversion_broadlink_exception(
    hass: HomeAssistant,
) -> None:
    """Test we load the device even if we cannot read the firmware version."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.get_fwversion.side_effect = blke.BroadlinkException()

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.LOADED
    forward_entries = set(mock_forward.mock_calls[0][1][1])
    domains = get_domains(mock_setup.api.type)
    assert mock_forward.call_count == 1
    assert forward_entries == domains


async def test_device_setup_get_fwversion_os_error(hass: HomeAssistant) -> None:
    """Test we load the device even if we cannot read the firmware version."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.get_fwversion.side_effect = OSError()

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_setup.entry.state is ConfigEntryState.LOADED
    forward_entries = set(mock_forward.mock_calls[0][1][1])
    domains = get_domains(mock_setup.api.type)
    assert mock_forward.call_count == 1
    assert forward_entries == domains


async def test_device_setup_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we register the device and the entries correctly."""
    device = get_device("Office")

    mock_setup = await device.setup_entry(hass)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == 1

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    assert device_entry.identifiers == {(DOMAIN, device.mac)}
    assert device_entry.name == device.name
    assert device_entry.model == device.model
    assert device_entry.manufacturer == device.manufacturer
    assert device_entry.sw_version == str(device.fwversion)

    for entry in er.async_entries_for_device(entity_registry, device_entry.id):
        assert (
            hass.states.get(entry.entity_id)
            .attributes[ATTR_FRIENDLY_NAME]
            .startswith(device.name)
        )


async def test_device_unload_works(hass: HomeAssistant) -> None:
    """Test we unload the device."""
    device = get_device("Office")

    with patch.object(hass.config_entries, "async_forward_entry_setups"):
        mock_setup = await device.setup_entry(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        await hass.config_entries.async_unload(mock_setup.entry.entry_id)

    assert mock_setup.entry.state is ConfigEntryState.NOT_LOADED
    assert mock_setup.api.aclose.await_count == 1
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    domains = get_domains(mock_setup.api.type)
    assert mock_forward.call_count == len(domains)
    assert forward_entries == domains


async def test_device_unload_failed(hass: HomeAssistant) -> None:
    """Test unloading fails when the device platforms cannot be unloaded."""
    device = get_device("Office")

    with patch.object(hass.config_entries, "async_forward_entry_setups"):
        mock_setup = await device.setup_entry(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=False
    ):
        await hass.config_entries.async_unload(mock_setup.entry.entry_id)

    assert mock_setup.entry.state is ConfigEntryState.FAILED_UNLOAD
    assert mock_setup.entry.reason == "Failed to unload the device"
    assert mock_setup.api.aclose.await_count == 0


async def test_device_unload_authentication_error(hass: HomeAssistant) -> None:
    """Test we unload a device that failed the authentication step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        await hass.config_entries.async_unload(mock_setup.entry.entry_id)

    assert mock_setup.entry.state is ConfigEntryState.NOT_LOADED
    assert mock_forward.call_count == 0


async def test_device_unload_update_failed(hass: HomeAssistant) -> None:
    """Test we unload a device that failed the update step."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = blke.NetworkTimeoutError()

    with patch.object(hass.config_entries, "async_forward_entry_setups"):
        mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        await hass.config_entries.async_unload(mock_setup.entry.entry_id)

    assert mock_setup.entry.state is ConfigEntryState.NOT_LOADED
    assert mock_forward.call_count == 0


async def test_device_update_listener(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we update device and entity registry when the entry is renamed."""
    device = get_device("Office")

    mock_setup = await device.setup_entry(hass)
    await hass.async_block_till_done()

    with patch(DEVICE_FACTORY, return_value=mock_setup.api):
        hass.config_entries.async_update_entry(mock_setup.entry, title="New Name")
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    assert device_entry.name == "New Name"
    for entry in er.async_entries_for_device(entity_registry, device_entry.id):
        assert (
            hass.states.get(entry.entity_id)
            .attributes[ATTR_FRIENDLY_NAME]
            .startswith("New Name")
        )


AUTO_SYNC_TIME = {CONF_AUTO_SYNC_TIME: True}


async def test_thermostat_time_sync(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the thermostat clock is set on setup and every half hour."""
    await hass.config.async_set_time_zone("Europe/Warsaw")
    # Sunday 2:30 local time (CEST), half an hour before DST ends.
    freezer.move_to("2026-10-25 00:30:00+00:00")
    device = get_device("Guest room")

    mock_setup = await device.setup_entry(
        hass, mock_entry=device.get_mock_entry(AUTO_SYNC_TIME)
    )

    mock_setup.api.set_time.assert_awaited_once_with(hour=2, minute=30, second=0, day=7)

    # The clock falls back from 3:00 CEST to 2:00 CET, and is synced right away.
    freezer.move_to("2026-10-25 01:00:05+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_setup.api.set_time.await_args_list[1] == call(
        hour=2, minute=0, second=5, day=7
    )

    await hass.config_entries.async_unload(mock_setup.entry.entry_id)
    freezer.move_to("2026-10-25 01:30:05+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_setup.api.set_time.await_count == 2


async def test_thermostat_time_sync_half_hour_dst(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a 30 minute DST change is synced right away."""
    await hass.config.async_set_time_zone("Australia/Lord_Howe")
    # Sunday 1:45 local time (+10:30), before the clock jumps from 2:00 to 2:30.
    freezer.move_to("2026-10-03 15:15:00+00:00")
    device = get_device("Guest room")

    mock_setup = await device.setup_entry(
        hass, mock_entry=device.get_mock_entry(AUTO_SYNC_TIME)
    )
    mock_setup.api.set_time.assert_awaited_once_with(hour=1, minute=45, second=0, day=7)

    freezer.move_to("2026-10-03 15:30:05+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_setup.api.set_time.await_args_list[1] == call(
        hour=2, minute=30, second=5, day=7
    )


async def test_thermostat_time_sync_time_zone_change(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the thermostat clock is set when the time zone changes."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-10-21 12:10:00+00:00")
    device = get_device("Guest room")

    mock_setup = await device.setup_entry(
        hass, mock_entry=device.get_mock_entry(AUTO_SYNC_TIME)
    )
    mock_setup.api.set_time.assert_awaited_once_with(
        hour=12, minute=10, second=0, day=3
    )

    await hass.config.async_update(time_zone="Europe/Warsaw")
    await hass.async_block_till_done()

    assert mock_setup.api.set_time.await_args_list[1] == call(
        hour=14, minute=10, second=0, day=3
    )


async def test_thermostat_time_sync_disabled_by_default(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the thermostat clock is left alone unless the user opts in."""
    device = get_device("Guest room")

    mock_setup = await device.setup_entry(hass)

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_setup.api.set_time.assert_not_awaited()


async def test_thermostat_time_sync_enabled_in_options(
    hass: HomeAssistant,
) -> None:
    """Test enabling the option reloads the entry and syncs the clock."""
    device = get_device("Guest room")
    mock_setup = await device.setup_entry(hass)
    mock_setup.api.set_time.assert_not_awaited()

    with patch(DEVICE_FACTORY, return_value=mock_setup.api):
        result = await hass.config_entries.options.async_init(mock_setup.entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_AUTO_SYNC_TIME: True}
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_setup.entry.state is ConfigEntryState.LOADED
    mock_setup.api.set_time.assert_awaited_once()


async def test_thermostat_time_sync_does_not_block_setup(
    hass: HomeAssistant,
) -> None:
    """Test the setup does not wait for the first clock sync."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    release = asyncio.Event()
    synced = False

    async def slow_set_time(**kwargs: int) -> None:
        nonlocal synced
        await release.wait()
        synced = True

    mock_api.set_time.side_effect = slow_set_time

    mock_setup = await device.setup_entry(
        hass, mock_api=mock_api, mock_entry=device.get_mock_entry(AUTO_SYNC_TIME)
    )

    assert mock_setup.entry.state is ConfigEntryState.LOADED
    assert not synced

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert synced


async def test_thermostat_time_sync_failure(hass: HomeAssistant) -> None:
    """Test a failure to set the thermostat clock does not fail the setup."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.set_time.side_effect = blke.NetworkTimeoutError()

    mock_setup = await device.setup_entry(
        hass, mock_api=mock_api, mock_entry=device.get_mock_entry(AUTO_SYNC_TIME)
    )

    assert mock_setup.entry.state is ConfigEntryState.LOADED
    mock_api.set_time.assert_awaited_once()


async def test_time_sync_only_for_thermostats(hass: HomeAssistant) -> None:
    """Test the clock is not set on devices other than thermostats."""
    device = get_device("Office")

    mock_setup = await device.setup_entry(
        hass, mock_entry=device.get_mock_entry(AUTO_SYNC_TIME)
    )

    mock_setup.api.set_time.assert_not_awaited()
