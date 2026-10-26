"""Tests for the Overkiz data update coordinator."""

from unittest.mock import Mock, patch

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import ExecutionState
from pyoverkiz.exceptions import (
    InvalidEventListenerIdError,
    MaintenanceError,
    ServiceUnavailableError,
    SomfyServiceError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_OPEN_COVER,
    CoverState,
)
from homeassistant.components.overkiz.const import (
    DOMAIN,
    RATE_LIMIT_RETRY_AFTER,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_ALL_ASSUMED_STATE,
    UPDATE_INTERVAL_EXECUTION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    async_deliver_events,
    device_created_event,
    device_removed_event,
    execution_state_changed_event,
)

TEMPERATURE_SENSOR = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#2",
    "sensor.maple_residence_garden_radiator_bathroom_temperature_sensor_temperature",
)

# A TaHoma v2 setup whose gateways list only holds the main box, while a
# swinging gate device is hosted by a secondary box absent from setup.gateways.
TAHOMA_V2_FIXTURE = "setup/cloud_somfy_tahoma_v2_europe.json"
MAIN_GATEWAY_ID = "1234-1234-6233"
SECONDARY_GATEWAY_ID = "1234-1234-8983"
MAIN_GATEWAY_CHILD_URL = "io://1234-1234-6233/12184029"
SECONDARY_GATEWAY_CHILD_URL = "io://1234-1234-8983/1959462"
SHUTTER = FixtureDevice(
    TAHOMA_V2_FIXTURE, MAIN_GATEWAY_CHILD_URL, "cover.office_garden_house_shutter"
)
GARAGE = FixtureDevice(
    TAHOMA_V2_FIXTURE,
    "io://1234-1234-6233/1166863",
    "cover.living_room_main_garage_door",
)
RTS_SHUTTER = FixtureDevice(
    "setup/cloud_somfy_connexoon_rts_asia.json",
    "rts://1234-1234-6362/16730022",
    "cover.palm_court_patio_shutter",
)


@pytest.mark.parametrize(
    "exception",
    [
        TooManyConcurrentRequestsError("Too many concurrent requests"),
        MaintenanceError("Server is down for maintenance"),
        ServiceUnavailableError("Server is unavailable"),
        SomfyServiceError("Somfy token refresh failed"),
        InvalidEventListenerIdError("Invalid event listener id"),
        TimeoutError("Timed out"),
        ClientConnectorError(Mock(), Mock()),
    ],
    ids=[
        "too_many_concurrent_requests",
        "maintenance",
        "service_unavailable",
        "somfy_service_error",
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


async def test_rate_limit_delays_next_refresh(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A rate limited refresh waits RATE_LIMIT_RETRY_AFTER before polling again."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    initial_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)

    mock_client.fetch_events.side_effect = TooManyRequestsError("Too many requests")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE

    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    mock_client.fetch_events.reset_mock()

    # Polling at the normal interval would keep the quota exhausted.
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.await_count == 0

    freezer.tick(RATE_LIMIT_RETRY_AFTER - UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.await_count == 1
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == initial_state.state


async def test_commands_share_the_execution_poll(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Commands don't fetch events themselves; one poll runs while they execute."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)
    mock_client.fetch_events.reset_mock()

    for cover in (SHUTTER, GARAGE):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: cover.entity_id},
            blocking=True,
        )

    assert mock_client.fetch_events.await_count == 0
    # The in-progress state comes from the local executions, not from a fetch.
    assert hass.states.get(SHUTTER.entity_id).state == CoverState.OPENING
    assert hass.states.get(GARAGE.entity_id).state == CoverState.OPENING

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            execution_state_changed_event(
                exec_id, ExecutionState.COMPLETED, ExecutionState.IN_PROGRESS
            )
            for exec_id in ("exec-1", "exec-2")
        ],
        update_interval=UPDATE_INTERVAL_EXECUTION,
    )

    assert mock_client.fetch_events.await_count == 1

    # Without pending executions, polling falls back to the default interval.
    freezer.tick(UPDATE_INTERVAL_EXECUTION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.await_count == 1

    freezer.tick(UPDATE_INTERVAL - UPDATE_INTERVAL_EXECUTION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.await_count == 2


async def test_stateless_hub_skips_the_execution_poll(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """RTS devices report no state, so commands don't speed up polling."""
    await setup_overkiz_integration(fixture=RTS_SHUTTER.fixture)
    mock_client.fetch_events.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: RTS_SHUTTER.entity_id},
        blocking=True,
    )
    assert mock_client.execute_action_group.await_count == 1

    freezer.tick(UPDATE_INTERVAL_EXECUTION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.fetch_events.await_count == 0

    freezer.tick(UPDATE_INTERVAL_ALL_ASSUMED_STATE - UPDATE_INTERVAL_EXECUTION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

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
