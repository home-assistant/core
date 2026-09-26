"""Tests for the Overkiz data update coordinator."""

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import Mock, patch

from aiohttp import ClientConnectorError, ServerDisconnectedError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import OverkizState
from pyoverkiz.exceptions import (
    InvalidEventListenerIdError,
    MaintenanceError,
    ServiceUnavailableError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
from pyoverkiz.models import Command, Setup
import pytest

from homeassistant.components.overkiz.const import (
    DOMAIN,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_ALL_ASSUMED_STATE,
    UPDATE_INTERVAL_EXECUTION,
    UPDATE_INTERVAL_RATE_LIMITED_MAX,
)
from homeassistant.components.overkiz.executor import OverkizExecutor
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    async_deliver_events,
    device_created_event,
    device_removed_event,
    device_state_changed_event,
    execution_registered_event,
    gateway_alive_event,
    gateway_down_event,
)

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

# A TaHoma v2 setup whose gateways list only holds the main box, while a
# swinging gate device is hosted by a secondary box absent from setup.gateways.
TAHOMA_V2_FIXTURE = "setup/cloud_somfy_tahoma_v2_europe.json"
MAIN_GATEWAY_ID = "1234-1234-6233"

# A commandable device hosted by the main gateway.
POOL_PUMP = FixtureDevice(
    TAHOMA_V2_FIXTURE,
    "io://1234-1234-6233/16168460",
    "switch.music_room_pool_pump_on_off",
)
POOL_HOUSE = FixtureDevice(
    TAHOMA_V2_FIXTURE,
    "io://1234-1234-6233/16580352",
    "switch.pool_house",
)
SECONDARY_GATEWAY_ID = "1234-1234-8983"
MAIN_GATEWAY_CHILD_URL = "io://1234-1234-6233/12184029"
SECONDARY_GATEWAY_CHILD_URL = "io://1234-1234-8983/1959462"


@pytest.mark.parametrize(
    "exception",
    [
        TooManyConcurrentRequestsError("Too many concurrent requests"),
        MaintenanceError("Server is down for maintenance"),
        ServiceUnavailableError("Server is unavailable"),
        InvalidEventListenerIdError("Invalid event listener id"),
        TimeoutError("Timed out"),
        ClientConnectorError(Mock(), Mock()),
    ],
    ids=[
        "too_many_concurrent_requests",
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


async def test_rate_limit_backs_off_and_recovers(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Being rate limited slows polling down; a successful fetch restores it."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    initial_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert initial_state.state != STATE_UNAVAILABLE

    # First rate limited refresh: entities go unavailable and polling doubles.
    mock_client.fetch_events.side_effect = TooManyRequestsError("Too many requests")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE

    # Nothing is requested at the old cadence any more...
    mock_client.fetch_events.reset_mock()
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.call_count == 0

    # ...only once twice the interval has passed, and that failure doubles again.
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.call_count == 1

    # A successful fetch clears the back off and restores the default interval.
    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    freezer.tick(UPDATE_INTERVAL * 4)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == initial_state.state

    mock_client.fetch_events.reset_mock()
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.call_count == 1


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
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    execute: Callable[[OverkizExecutor], Awaitable[None]],
) -> None:
    """Commanding several entities at once coalesces into a single refresh."""
    entry = await setup_overkiz_integration(fixture=POOL_PUMP.fixture)
    coordinator = entry.runtime_data.coordinator
    mock_client.reset_mock()

    await asyncio.gather(
        *(
            execute(OverkizExecutor(device.device_url, coordinator))
            for device in (POOL_PUMP, POOL_HOUSE)
        )
    )

    assert mock_client.execute_action_group.await_count == 2
    assert mock_client.fetch_events.await_count == 1


async def test_rate_limit_back_off_never_polls_faster_than_configured(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An hourly hub is not sped up to the rate limit cap by backing off."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator = entry.runtime_data.coordinator
    coordinator.set_update_interval(UPDATE_INTERVAL_ALL_ASSUMED_STATE)

    mock_client.fetch_events.side_effect = TooManyRequestsError("Too many requests")
    freezer.tick(UPDATE_INTERVAL_ALL_ASSUMED_STATE)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.update_interval >= UPDATE_INTERVAL_ALL_ASSUMED_STATE
    assert coordinator.update_interval > UPDATE_INTERVAL_RATE_LIMITED_MAX


async def test_rate_limit_recovery_restores_execution_polling(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Recovering while an execution is pending resumes the faster cadence."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator = entry.runtime_data.coordinator
    coordinator.executions["exec-1"] = []

    mock_client.fetch_events.side_effect = TooManyRequestsError("Too many requests")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.update_interval > UPDATE_INTERVAL

    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.update_interval == UPDATE_INTERVAL_EXECUTION


async def test_reconnect_clears_rate_limit_back_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Recovering through the reconnect path also restores the cadence."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator = entry.runtime_data.coordinator

    mock_client.fetch_events.side_effect = TooManyRequestsError("Too many requests")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.update_interval > UPDATE_INTERVAL

    # A reconnect returns devices without ever reaching the event loop below it.
    mock_client.fetch_events.side_effect = ServerDisconnectedError
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_rate_limit_during_a_reconnect_backs_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A reconnect can be rate limited too, and has to back off like any refresh.

    Retrying a login at the unchanged interval is what got us rate limited.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator = entry.runtime_data.coordinator

    mock_client.fetch_events.side_effect = ServerDisconnectedError
    mock_client.login.side_effect = TooManyRequestsError("Too many requests")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert coordinator.update_interval == UPDATE_INTERVAL * 2


async def test_execution_registered_elsewhere_polls_faster(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An execution started outside Home Assistant also needs the faster cadence.

    Its states change just as fast as one we asked for, and the event is the
    only notice we get of it.
    """
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator = entry.runtime_data.coordinator

    assert coordinator.update_interval == UPDATE_INTERVAL

    await async_deliver_events(
        hass, freezer, mock_client, [execution_registered_event("exec-elsewhere")]
    )

    assert coordinator.update_interval == UPDATE_INTERVAL_EXECUTION


async def test_stateless_recovery_restores_default_interval(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A stateless hub is not left backed off by a pending execution."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator = entry.runtime_data.coordinator
    coordinator.is_stateless = True
    coordinator.executions["exec-1"] = []

    mock_client.fetch_events.side_effect = TooManyRequestsError("Too many requests")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.update_interval > UPDATE_INTERVAL

    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_water_heater_refreshes_are_debounced(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Water heaters refresh through the debouncer, not once per entity.

    These platforms pass refresh_afterwards=False and refresh themselves once
    the whole command sequence is sent, so they bypass the executor.
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

    assert mock_client.fetch_events.await_count == 1


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


async def test_gateway_down_marks_its_entities_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """An unreachable gateway takes its devices' entities down with it.

    The server keeps answering for those devices out of its cache, so nothing
    in the device payload changes and only the gateway event reveals it.
    """
    await setup_overkiz_integration(fixture=POOL_PUMP.fixture)

    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass, freezer, mock_client, [gateway_down_event(MAIN_GATEWAY_ID)]
    )

    assert hass.states.get(POOL_PUMP.entity_id).state == STATE_UNAVAILABLE

    await async_deliver_events(
        hass, freezer, mock_client, [gateway_alive_event(MAIN_GATEWAY_ID)]
    )

    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE


async def test_state_from_device_clears_its_gateway(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Traffic from a device proves the gateway that carried it is back.

    GATEWAY_ALIVE is otherwise the only way out, so a missed one would strand
    every entity on that gateway until the config entry reloads.
    """
    await setup_overkiz_integration(fixture=POOL_PUMP.fixture)

    await async_deliver_events(
        hass, freezer, mock_client, [gateway_down_event(MAIN_GATEWAY_ID)]
    )

    assert hass.states.get(POOL_PUMP.entity_id).state == STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                POOL_PUMP.device_url,
                [{"name": OverkizState.CORE_ON_OFF.value, "type": 3, "value": "on"}],
            )
        ],
    )

    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE


async def test_gateway_already_down_at_setup_marks_its_entities_unavailable(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """A gateway down before setup has no event left to announce it."""

    def mark_gateways_down(setup: Setup) -> None:
        for gateway in setup.gateways:
            gateway.alive = False

    await setup_overkiz_integration(
        fixture=POOL_PUMP.fixture, mutate=mark_gateways_down
    )

    assert hass.states.get(POOL_PUMP.entity_id).state == STATE_UNAVAILABLE


async def test_gateway_down_leaves_other_gateways_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Only the devices hosted by the downed gateway go unavailable."""
    await setup_overkiz_integration(fixture=POOL_PUMP.fixture)

    await async_deliver_events(
        hass, freezer, mock_client, [gateway_down_event("0000-0000-0000")]
    )

    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE
