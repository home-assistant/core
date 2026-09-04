"""Tests for the Overkiz data update coordinator."""

from datetime import timedelta
from unittest.mock import Mock, patch

from aiohttp import ClientConnectorError, ServerDisconnectedError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName
from pyoverkiz.exceptions import (
    BadCredentialsError,
    InvalidEventListenerIdError,
    MaintenanceError,
    NotAuthenticatedError,
    OverkizError,
    ServiceUnavailableError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
from pyoverkiz.models import ExecutionRegisteredEvent
import pytest

from homeassistant.components.overkiz.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.overkiz.coordinator import OverkizDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import async_deliver_events, device_created_event, device_removed_event

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


async def test_execution_dropout_ttl_recovery(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Lost EXECUTION_STATE_CHANGED event recovers via execution TTL and returns interval to 30s."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    assert coordinator.update_interval == UPDATE_INTERVAL

    # Deliver EXECUTION_REGISTERED event
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-123"
            )
        ],
    )

    # Coordinator update_interval drops to 1s
    assert coordinator.update_interval == timedelta(seconds=1)
    assert "exec-123" in coordinator.executions

    # Fast forward beyond EXECUTION_TTL without an EXECUTION_STATE_CHANGED completion event
    freezer.tick(timedelta(seconds=65))
    mock_client.queue_events([])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify execution was cleaned up and interval returned to 30s
    assert "exec-123" not in coordinator.executions
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_execution_cleared_on_error(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Errors clear pending executions and restore update_interval."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            ExecutionRegisteredEvent(
                name=EventName.EXECUTION_REGISTERED, exec_id="exec-456"
            )
        ],
    )
    assert coordinator.update_interval == timedelta(seconds=1)
    assert "exec-456" in coordinator.executions

    # Transient error happens on fetch
    mock_client.fetch_events.side_effect = ClientConnectorError(Mock(), Mock())
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Executions cleared and update_interval restored
    assert coordinator.executions == {}
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_coordinator_resync_devices_after_listener_invalidation(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Listener invalidation sets _need_full_resync and fetches all devices on next refresh."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    mock_client.get_devices.reset_mock()

    # Simulate InvalidEventListenerIdError
    mock_client.fetch_events.side_effect = InvalidEventListenerIdError(
        "Invalid event listener id"
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator._need_full_resync is True

    # Recovery: next poll should call get_devices to resynchronize full state
    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.get_devices.await_count == 1
    assert coordinator._need_full_resync is False


async def test_relogin_recovery_on_transient_not_authenticated_error(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Transient NotAuthenticatedError triggers re-login without raising ConfigEntryAuthFailed."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    mock_client.login.reset_mock()
    mock_client.get_devices.reset_mock()

    # Session expired: fetch_events throws NotAuthenticatedError
    # But client.login() and get_devices() succeed during recovery
    mock_client.fetch_events.side_effect = NotAuthenticatedError("Session expired")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Integration stays LOADED, did not raise ConfigEntryAuthFailed
    assert entry.state is ConfigEntryState.LOADED
    assert mock_client.login.await_count == 1
    assert mock_client.get_devices.await_count == 1
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state != STATE_UNAVAILABLE

    # When login fails with transient network error: raises UpdateFailed (transient), NOT ConfigEntryAuthFailed
    mock_client.login.side_effect = ClientConnectorError(Mock(), Mock())
    mock_client.fetch_events.side_effect = NotAuthenticatedError("Session expired")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Still in LOADED state (coordinator is in retry state, not failed entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE


async def test_server_disconnected_relogin_transport_error(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """ServerDisconnectedError catches transport errors during relogin safely as UpdateFailed."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    mock_client.login.side_effect = TimeoutError("Connection timed out during relogin")
    mock_client.fetch_events.side_effect = ServerDisconnectedError(
        "Server disconnected"
    )

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Cleanly caught as UpdateFailed -> entity unavailable, entry stays LOADED (will retry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE
    assert coordinator._need_full_resync is True


async def test_bad_credentials_during_relogin_triggers_auth_failed(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Permanent BadCredentialsError during relogin triggers ConfigEntryAuthFailed."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    mock_client.login.side_effect = BadCredentialsError("Bad credentials")
    mock_client.fetch_events.side_effect = NotAuthenticatedError("Session expired")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE


async def test_generic_overkiz_error_handled_as_transient(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Generic OverkizError is caught and handled as UpdateFailed."""
    entry = await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)
    coordinator: OverkizDataUpdateCoordinator = entry.runtime_data.coordinator

    mock_client.fetch_events.side_effect = OverkizError("Internal server glitch")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE
    assert coordinator._need_full_resync is True
