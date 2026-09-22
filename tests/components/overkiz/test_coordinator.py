"""Tests for the Overkiz data update coordinator."""

from unittest.mock import Mock, patch

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import ExecutionState, FailureType, OverkizState
from pyoverkiz.exceptions import (
    InvalidEventListenerIdError,
    MaintenanceError,
    ServiceUnavailableError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
import pytest

from homeassistant.components.overkiz.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    async_deliver_events,
    device_created_event,
    device_removed_event,
    device_state_changed_event,
    execution_state_changed_event,
    gateway_alive_event,
    gateway_down_event,
)

from tests.common import MockConfigEntry, async_fire_time_changed

TEMPERATURE_SENSOR = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#2",
    "sensor.maple_residence_garden_radiator_bathroom_temperature_sensor_temperature",
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


async def _async_command_pool_pump(hass: HomeAssistant) -> None:
    """Turn the pool pump on, registering an execution for its device."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: POOL_PUMP.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "failure_type_code",
    [
        FailureType.PEER_DOWN,
        FailureType.ACTUATORNOANSWER,
        FailureType.TIME_OUT_ON_TRANSMIT,
    ],
)
async def test_undelivered_command_marks_device_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    failure_type_code: FailureType,
) -> None:
    """A command the gateway could not deliver means the device is unreachable.

    This is the only report of it: the server goes on answering for the device
    and never sends DeviceUnavailableEvent, so without this the entity stays
    available while every command is silently dropped.
    """
    await setup_overkiz_integration(fixture=POOL_PUMP.fixture)
    await _async_command_pool_pump(hass)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            execution_state_changed_event(
                exec_id="exec-1",
                new_state=ExecutionState.FAILED,
                old_state=ExecutionState.IN_PROGRESS,
                failure_type_code=failure_type_code,
            )
        ],
    )

    assert hass.states.get(POOL_PUMP.entity_id).state == STATE_UNAVAILABLE


async def test_refused_command_keeps_device_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """A device that refuses a command answered it, so it stays available."""
    await setup_overkiz_integration(fixture=POOL_PUMP.fixture)
    await _async_command_pool_pump(hass)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            execution_state_changed_event(
                exec_id="exec-1",
                new_state=ExecutionState.FAILED,
                old_state=ExecutionState.IN_PROGRESS,
                failure_type_code=FailureType.PRIORITY_LOCK__USER,
            )
        ],
    )

    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE


async def test_state_from_device_clears_unreachable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """A state reported by the device proves it is reachable again.

    Recovery cannot wait for the next command: a device nobody commands again
    would stay unavailable forever.
    """
    await setup_overkiz_integration(fixture=POOL_PUMP.fixture)
    await _async_command_pool_pump(hass)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            execution_state_changed_event(
                exec_id="exec-1",
                new_state=ExecutionState.FAILED,
                old_state=ExecutionState.IN_PROGRESS,
                failure_type_code=FailureType.PEER_DOWN,
            )
        ],
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


async def test_completed_command_clears_unreachable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """A command that lands proves the device is reachable again.

    Two commands can be in flight at once, so a later one landing has to undo
    the conclusion an earlier failure drew.
    """
    await setup_overkiz_integration(fixture=POOL_PUMP.fixture)
    await _async_command_pool_pump(hass)
    await _async_command_pool_pump(hass)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            execution_state_changed_event(
                exec_id="exec-1",
                new_state=ExecutionState.FAILED,
                old_state=ExecutionState.IN_PROGRESS,
                failure_type_code=FailureType.PEER_DOWN,
            )
        ],
    )

    assert hass.states.get(POOL_PUMP.entity_id).state == STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            execution_state_changed_event(
                exec_id="exec-2",
                new_state=ExecutionState.COMPLETED,
                old_state=ExecutionState.IN_PROGRESS,
            )
        ],
    )

    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE
