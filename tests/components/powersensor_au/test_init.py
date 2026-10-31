"""Tests for setup, unload, and migration of the Powersensor integration."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.powersensor_au.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor_au.const import (
    CFG_ROLES,
    DOMAIN,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_WATER,
    VHH_DEVICE_ID,
)
from homeassistant.components.powersensor_au.models import PowersensorRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

PLUG_MAC = "aabbccddeeff"
SENSOR_MAC = "112233445566"


async def test_setup_entry_populates_runtime_data(
    config_entry: MockConfigEntry,
) -> None:
    """Setup stores a populated PowersensorRuntimeData on the entry."""
    assert config_entry.state is ConfigEntryState.LOADED
    assert isinstance(config_entry.runtime_data, PowersensorRuntimeData)
    assert config_entry.runtime_data.vhh is not None
    assert config_entry.runtime_data.dispatcher is not None
    assert config_entry.runtime_data.devices is not None


@pytest.mark.usefixtures("config_entry")
async def test_setup_starts_mdns_browser(mock_devices: MagicMock) -> None:
    """devices.start() is called once during setup with an async callback."""
    mock_devices.start.assert_awaited_once()
    cb = mock_devices.start.call_args[0][0]
    assert callable(cb)


async def test_unload_unsubscribes_devices_then_stops_library(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Unloading unsubscribes every discovered device, then stops the library."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()
    mock_devices.reset_mock()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_devices.mock_calls == [
        call.unsubscribe(PLUG_MAC),
        call.unsubscribe(SENSOR_MAC),
        call.stop(),
    ]


async def test_event_during_unload_does_not_orphan_entities(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device announced while unloading must not leave entities behind.

    The library can deliver events until stop() returns.  If those reached a
    platform that had already been unloaded, its entities would never be
    removed, and the device's entities would be rejected as duplicates on the
    next load.
    """
    callback = mock_devices.start.call_args[0][0]
    device_found = {"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"}

    async def announce_while_stopping() -> None:
        await callback(device_found)

    mock_devices.stop = AsyncMock(side_effect=announce_while_stopping)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_devices.stop = AsyncMock()
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_devices.start.call_args[0][0](device_found)
    await hass.async_block_till_done()

    assert "does not generate unique IDs" not in caplog.text


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_devices_start_failure_retries_and_recovers(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A transient devices.start() failure retries and the entry then works normally.

    The sensor platform must not be forwarded before the failure, otherwise the
    retry finds it already registered and never re-runs its setup, leaving a
    LOADED entry that creates no entities.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"roles": {}},
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    mock_devices.start = AsyncMock(side_effect=[RuntimeError("no socket"), None])

    with patch(
        "homeassistant.components.powersensor_au.PowersensorZeroconfDevices",
        return_value=mock_devices,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_RETRY
        mock_devices.stop.assert_awaited_once()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert mock_devices.start.await_count == 2

    cb = mock_devices.start.call_args[0][0]
    await cb({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert {e.unique_id for e in entities} >= {
        f"{PLUG_MAC}_power",
        f"{PLUG_MAC}_total_energy",
    }


@pytest.mark.usefixtures("mock_async_zeroconf")
@pytest.mark.parametrize(
    ("roles", "with_solar"),
    [
        pytest.param({}, False, id="no_roles"),
        pytest.param({SENSOR_MAC: ROLE_HOUSENET}, False, id="mains_only"),
        pytest.param({SENSOR_MAC: ROLE_SOLAR}, True, id="solar"),
    ],
)
async def test_setup_constructs_vhh_with_solar_from_saved_roles(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    roles: dict[str, str],
    with_solar: bool,
) -> None:
    """VirtualHousehold gets with_solar=True only when a solar role is saved.

    It also gets the integration's logger, so errors in its callbacks are logged.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CFG_ROLES: roles},
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.powersensor_au.PowersensorZeroconfDevices",
            return_value=mock_devices,
        ),
        patch(
            "homeassistant.components.powersensor_au.VirtualHousehold",
            autospec=True,
        ) as mock_vhh,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_vhh.assert_called_once_with(
        with_solar,
        logger=logging.getLogger("homeassistant.components.powersensor_au"),
    )


async def _delete_device(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, device_id: str
) -> bool:
    """Ask HA to delete a device, as its device page does; return whether it did."""
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_id)
    return response["success"]


@pytest.mark.parametrize(
    ("mac", "device_type"),
    [
        pytest.param(PLUG_MAC, "plug", id="plug"),
        pytest.param(SENSOR_MAC, "sensor", id="sensor"),
    ],
)
async def test_device_on_the_network_cannot_be_deleted(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mac: str,
    device_type: str,
) -> None:
    """A device the library still reports would come back, so it can't be deleted."""
    await fire({"event": "device_found", "mac": mac, "device_type": device_type})
    await hass.async_block_till_done()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mac), config_entry.entry_id
    )
    assert device is not None

    assert not await _delete_device(hass, hass_ws_client, device.id)
    assert device_registry.async_get(device.id) is not None


@pytest.mark.parametrize(
    ("discovery", "mac"),
    [
        pytest.param(
            [{"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"}],
            PLUG_MAC,
            id="plug",
        ),
        pytest.param(
            [
                {"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"},
                {
                    "event": "now_relaying_for",
                    "device_type": "sensor",
                    "mac": SENSOR_MAC,
                    "role": ROLE_HOUSENET,
                },
            ],
            SENSOR_MAC,
            id="sensor",
        ),
    ],
)
async def test_lost_device_can_be_deleted_and_is_rebuilt_if_it_returns(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    discovery: list[dict[str, Any]],
    mac: str,
) -> None:
    """Once lost, a device can be deleted, and it is set up anew if it returns."""
    for event in discovery:
        await fire(event)
    await hass.async_block_till_done()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mac), config_entry.entry_id
    )
    assert device is not None
    entities = {
        e.unique_id for e in er.async_entries_for_device(entity_registry, device.id)
    }
    assert entities

    await fire({"event": "device_lost", "mac": mac})
    assert await _delete_device(hass, hass_ws_client, device.id)
    await hass.async_block_till_done()
    assert device_registry.async_get(device.id) is None

    for event in discovery:
        await fire(event)
    await hass.async_block_till_done()
    returned = device_registry.async_get_device_by_identifier(
        (DOMAIN, mac), config_entry.entry_id
    )
    assert returned is not None
    assert {
        e.unique_id for e in er.async_entries_for_device(entity_registry, returned.id)
    } == entities


async def test_returning_sensor_gets_entities_of_a_role_it_had_before(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Deleting a sensor forgets which of its entities exist, but keeps its role."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_APPLIANCE,
        }
    )
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_WATER,
        }
    )
    await hass.async_block_till_done()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SENSOR_MAC), config_entry.entry_id
    )
    assert device is not None

    await fire({"event": "device_lost", "mac": SENSOR_MAC})
    assert await _delete_device(hass, hass_ws_client, device.id)
    await hass.async_block_till_done()
    assert config_entry.data[CFG_ROLES][SENSOR_MAC] == ROLE_WATER

    # It returns with its saved role, water, then reports appliance again.
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_APPLIANCE,
        }
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_power"
    )
    assert entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_total_water_consumption"
    )


async def test_household_view_cannot_be_deleted(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The household view belongs to the installation, not to one device."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await fire({"event": "device_lost", "mac": SENSOR_MAC})
    await hass.async_block_till_done()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, VHH_DEVICE_ID), config_entry.entry_id
    )
    assert device is not None

    assert not await _delete_device(hass, hass_ws_client, device.id)
    assert device_registry.async_get(device.id) is not None
