"""Tests for the Overkiz data update coordinator."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import Mock, patch

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.exceptions import (
    InvalidEventListenerIdError,
    MaintenanceError,
    ServiceUnavailableError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
from pyoverkiz.models import Command
import pytest

from homeassistant.components.overkiz.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.overkiz.executor import OverkizExecutor
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import REQUEST_REFRESH_DEFAULT_COOLDOWN

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import async_deliver_events, device_created_event, device_removed_event

from tests.common import MockConfigEntry, async_fire_time_changed

TEMPERATURE_SENSOR = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#2",
    "sensor.maple_residence_garden_radiator_bathroom_temperature_sensor_temperature",
)

# Two water heaters in one setup, on platforms that refresh themselves.
DHW_CE_FLAT_C2 = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/109286#1",
    "water_heater.my_home_patio_water_heating",
)
DHW_ATLANTIC_IO = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/6713703#1",
    "water_heater.my_home_water_heater",
)

# Two switches in one setup, so several entities can be commanded at once.
POOL_PUMP = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/16168460",
    "switch.music_room_pool_pump_on_off",
)
POOL_HOUSE = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/16580352",
    "switch.pool_house",
)

# A TaHoma v2 setup whose gateways list only holds the main box, while a
# swinging gate device is hosted by a secondary box absent from setup.gateways.
TAHOMA_V2_FIXTURE = "setup/cloud_somfy_tahoma_v2_europe.json"
MAIN_GATEWAY_ID = "1234-1234-6233"
SECONDARY_GATEWAY_ID = "1234-1234-8983"
MAIN_GATEWAY_CHILD_URL = "io://1234-1234-6233/12184029"
SECONDARY_GATEWAY_CHILD_URL = "io://1234-1234-8983/1959462"


@pytest.mark.parametrize(
    "exception",
    [
        TooManyConcurrentRequestsError("Too many concurrent requests"),
        TooManyRequestsError("Too many requests"),
        MaintenanceError("Server is down for maintenance"),
        ServiceUnavailableError("Server is unavailable"),
        InvalidEventListenerIdError("Invalid event listener id"),
        TimeoutError("Timed out"),
        ClientConnectorError(Mock(), Mock()),
    ],
    ids=[
        "too_many_concurrent_requests",
        "too_many_requests",
        "maintenance",
        "service_unavailable",
        "invalid_event_listener_id",
        "timeout",
        "client_connector_error",
    ],
)
async def test_transient_error_is_retried(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Transient errors are handled cleanly: entities go unavailable, then recover."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    initial_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert initial_state.state != STATE_UNAVAILABLE

    # A transient error during a refresh makes the entities unavailable.
    mock_client.fetch_events.side_effect = exception
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE

    # Once the server recovers, the next refresh restores the entities.
    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == initial_state.state


async def test_device_removed_deletes_device(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A DEVICE_REMOVED event deletes a device owned only by this config entry."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    device_id = entity_registry.async_get(TEMPERATURE_SENSOR.entity_id).device_id

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [device_removed_event(TEMPERATURE_SENSOR.device_url)],
    )

    assert device_registry.async_get(device_id) is None


async def test_device_removed_keeps_device_owned_by_other_entry(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A DEVICE_REMOVED event does not delete a device owned by another entry."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    device_id = entity_registry.async_get(TEMPERATURE_SENSOR.entity_id).device_id

    # Move the device to another config entry; removing the Overkiz entry must then
    # leave it in place instead of deleting a device it no longer owns.
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    device_registry.async_update_device(
        device_id, new_config_entry_id=other_entry.entry_id
    )

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [device_removed_event(TEMPERATURE_SENSOR.device_url)],
    )

    device = device_registry.async_get(device_id)
    assert device is not None
    assert device.config_entry_id == other_entry.entry_id


async def test_child_devices_link_to_their_gateway(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Every child device links to its gateway, even one absent from setup.gateways.

    The secondary box that hosts the swinging gate is not returned in
    setup.gateways, but the via_device link of its child must still resolve.
    A DEVICE_CREATED event reloads the entry, which must keep the link intact.
    """
    mock_config_entry.add_to_hass(hass)
    mock_client.set_setup_fixture(TAHOMA_V2_FIXTURE)

    with patch(
        "homeassistant.components.overkiz.create_cloud_client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        main_gateway = device_registry.async_get_device_by_identifier(
            (DOMAIN, MAIN_GATEWAY_ID), mock_config_entry.entry_id
        )
        secondary_gateway = device_registry.async_get_device_by_identifier(
            (DOMAIN, SECONDARY_GATEWAY_ID), mock_config_entry.entry_id
        )
        assert main_gateway is not None
        assert secondary_gateway is not None

        main_child = device_registry.async_get_device_by_identifier(
            (DOMAIN, MAIN_GATEWAY_CHILD_URL), mock_config_entry.entry_id
        )
        secondary_child = device_registry.async_get_device_by_identifier(
            (DOMAIN, SECONDARY_GATEWAY_CHILD_URL), mock_config_entry.entry_id
        )
        assert main_child is not None
        assert secondary_child is not None
        assert main_child.via_device_id == main_gateway.id
        assert secondary_child.via_device_id == secondary_gateway.id

        # A DEVICE_CREATED event reloads the entry; the links must survive.
        await async_deliver_events(
            hass,
            freezer,
            mock_client,
            [device_created_event(SECONDARY_GATEWAY_CHILD_URL)],
        )

    assert mock_config_entry.state is ConfigEntryState.LOADED

    secondary_gateway = device_registry.async_get_device_by_identifier(
        (DOMAIN, SECONDARY_GATEWAY_ID), mock_config_entry.entry_id
    )
    secondary_child = device_registry.async_get_device_by_identifier(
        (DOMAIN, SECONDARY_GATEWAY_CHILD_URL), mock_config_entry.entry_id
    )
    assert secondary_gateway is not None
    assert secondary_child is not None
    assert secondary_child.via_device_id == secondary_gateway.id


@pytest.mark.parametrize(
    "execute",
    [
        lambda executor: executor.async_execute_command("on"),
        lambda executor: executor.async_execute_commands([Command(name="on")]),
    ],
    ids=["single_command", "batched_commands"],
)
async def test_command_refreshes_are_debounced(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    execute: Callable[[OverkizExecutor], Awaitable[None]],
) -> None:
    """A burst of commands costs two refreshes, not one per command.

    The coordinator's debouncer leads, so the first command refreshes at once
    and everything else in the cooldown window is collapsed into one trailing
    refresh, however many commands that is.
    """
    entry = await setup_overkiz_integration(fixture=POOL_PUMP.fixture)
    coordinator = entry.runtime_data.coordinator
    mock_client.reset_mock()

    await asyncio.gather(
        *(
            execute(OverkizExecutor(device.device_url, coordinator))
            for device in (POOL_PUMP, POOL_HOUSE)
            for _ in range(3)
        )
    )

    assert mock_client.execute_action_group.await_count == 6
    assert mock_client.fetch_events.await_count == 1

    freezer.tick(timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.await_count == 2


async def test_water_heater_refreshes_are_debounced(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Water heaters refresh through the debouncer, not once per command.

    These platforms send several commands per service call, so they are the
    worst case for a refresh that is not coalesced.
    """
    await setup_overkiz_integration(fixture=DHW_CE_FLAT_C2.fixture)
    mock_client.reset_mock()

    await asyncio.gather(
        *(
            hass.services.async_call(
                "water_heater",
                "set_temperature",
                {"entity_id": device.entity_id, "temperature": 55.0},
                blocking=True,
            )
            for device in (DHW_CE_FLAT_C2, DHW_ATLANTIC_IO)
        )
    )

    # CE_FLAT_C2 sends two commands for a setpoint, the plain IO component one.
    assert mock_client.execute_action_group.await_count == 3
    assert mock_client.fetch_events.await_count == 1

    freezer.tick(timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.await_count == 2
