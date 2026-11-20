"""Tests for an Overkiz cloud entry that also uses the local API."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError, ServerDisconnectedError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.exceptions import (
    BadCredentialsError,
    NotAuthenticatedError,
    TooManyRequestsError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.overkiz.const import (
    API_RETRY_INTERVAL,
    DOMAIN,
    UPDATE_INTERVAL,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_OPEN_COVER,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import load_setup_fixture
from .conftest import FixtureDevice, MockOverkizClient

FIXTURE = "setup/cloud_somfy_tahoma_v2_europe.json"

# The cover is exposed by both APIs, the pool pump only by the cloud API
COVER = FixtureDevice(
    FIXTURE, "io://1234-1234-6233/12184029", "cover.office_garden_house_shutter"
)
POOL_PUMP = FixtureDevice(
    FIXTURE, "io://1234-1234-6233/16168460", "switch.music_room_pool_pump_on_off"
)


@pytest.fixture(autouse=True)
def mock_clients(
    mock_client: MockOverkizClient, mock_local_client: MockOverkizClient
) -> Generator[None]:
    """Mock the cloud API with all devices and the local API with the cover only."""
    mock_client.set_setup_fixture(FIXTURE)

    mock_local_client.set_setup_fixture(FIXTURE)
    mock_local_client.setup.root_place = None
    mock_local_client.setup.devices = [
        device
        for device in mock_local_client.setup.devices
        if device.device_url == COVER.device_url
    ]

    with (
        patch(
            "homeassistant.components.overkiz.create_cloud_client",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.overkiz.create_local_client",
            return_value=mock_local_client,
        ),
    ):
        yield


@pytest.fixture
async def entry(
    hass: HomeAssistant, mock_cloud_with_local_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Return the cloud entry that also uses the local API, not set up yet."""
    mock_cloud_with_local_config_entry.add_to_hass(hass)
    return mock_cloud_with_local_config_entry


async def _async_setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the config entry."""
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _async_pass_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Let the time pass, which refreshes the coordinators that are due."""
    freezer.tick(seconds)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_devices_are_split_between_both_apis(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
) -> None:
    """Test the local API handles its devices and the cloud API the other ones."""
    await _async_setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED

    data = entry.runtime_data
    assert list(data.local_coordinator.data) == [COVER.device_url]
    assert COVER.device_url not in data.coordinator.data
    assert POOL_PUMP.device_url in data.coordinator.data
    assert len(data.devices) == len(mock_client.setup.devices)

    # The device keeps the unique ID it has without the local API
    assert entity_registry.async_get(COVER.entity_id).unique_id == COVER.device_url
    assert hass.states.get(COVER.entity_id).state != STATE_UNAVAILABLE
    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE
    assert hass.states.get(f"{COVER.entity_id}_2") is None


async def test_entities_are_the_same_as_without_local_api(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_cloud_with_local_config_entry: MockConfigEntry,
) -> None:
    """Test adding the local API to an entry keeps its entities as they are."""
    mock_config_entry.add_to_hass(hass)
    await _async_setup(hass, mock_config_entry)
    cloud_entities = {
        entity.entity_id: entity.unique_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }

    hass.config_entries.async_update_entry(
        mock_config_entry, data=mock_cloud_with_local_config_entry.data
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.local_coordinator is not None
    assert cloud_entities
    assert {
        entity.entity_id: entity.unique_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    } == cloud_entities


async def test_areas_of_local_devices_come_from_the_cloud(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the local API, which has no places, uses the places of the cloud API."""
    await _async_setup(hass, entry)

    data = entry.runtime_data
    assert data.coordinator.areas
    assert data.local_coordinator.areas == data.coordinator.areas


async def test_commands_are_sent_through_the_api_of_the_device(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
    mock_local_client: MockOverkizClient,
) -> None:
    """Test a command only reaches the API that handles the device."""
    await _async_setup(hass, entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: COVER.entity_id},
        blocking=True,
    )

    assert mock_local_client.execute_action_group.await_count == 1
    assert mock_client.execute_action_group.await_count == 0

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: POOL_PUMP.entity_id},
        blocking=True,
    )

    assert mock_local_client.execute_action_group.await_count == 1
    assert mock_client.execute_action_group.await_count == 1


async def test_cloud_outage_keeps_local_devices_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
) -> None:
    """Test losing the cloud API only makes the devices of the cloud unavailable."""
    await _async_setup(hass, entry)

    mock_client.fetch_events.side_effect = TimeoutError
    await _async_pass_time(hass, freezer, UPDATE_INTERVAL.total_seconds())

    assert hass.states.get(POOL_PUMP.entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get(COVER.entity_id).state != STATE_UNAVAILABLE


async def test_local_outage_keeps_cloud_devices_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    mock_local_client: MockOverkizClient,
) -> None:
    """Test losing the local API only makes the devices of the local API unavailable."""
    await _async_setup(hass, entry)

    mock_local_client.fetch_events.side_effect = TimeoutError
    await _async_pass_time(hass, freezer, UPDATE_INTERVAL.total_seconds())

    assert hass.states.get(COVER.entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE


async def test_cloud_relogin_leaves_local_devices_to_the_local_api(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
) -> None:
    """Test the cloud API does not take the local devices back when it logs in again."""
    await _async_setup(hass, entry)

    mock_client.fetch_events.side_effect = ServerDisconnectedError
    await _async_pass_time(hass, freezer, UPDATE_INTERVAL.total_seconds())

    assert mock_client.get_devices.await_count == 1
    data = entry.runtime_data
    assert COVER.device_url not in data.coordinator.data
    assert POOL_PUMP.device_url in data.coordinator.data
    assert data.coordinator_for(data.local_coordinator.data[COVER.device_url]) is (
        data.local_coordinator
    )


@pytest.mark.parametrize("cloud_error", [ClientError, TooManyRequestsError])
async def test_setup_without_cloud_sets_up_local_devices(
    hass: HomeAssistant,
    cloud_error: type[Exception],
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
    mock_local_client: MockOverkizClient,
) -> None:
    """Test the local devices are set up when the cloud API cannot be reached."""
    mock_client.login.side_effect = cloud_error

    await _async_setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data
    assert data.coordinator.client is mock_local_client
    assert data.local_coordinator is None
    # Without the places of the cloud API, a new cover is named without its area
    cover_entity_id = entity_registry.async_get_entity_id(
        COVER_DOMAIN, DOMAIN, COVER.device_url
    )
    assert hass.states.get(cover_entity_id).state != STATE_UNAVAILABLE
    assert hass.states.get(POOL_PUMP.entity_id) is None

    # As long as the cloud API cannot be reached, the entry stays as it is
    await _async_pass_time(hass, freezer, API_RETRY_INTERVAL.total_seconds())

    assert entry.runtime_data is data
    assert hass.states.get(POOL_PUMP.entity_id) is None

    # The cloud devices are set up as soon as the cloud API is back
    mock_client.login.side_effect = None
    await _async_pass_time(hass, freezer, API_RETRY_INTERVAL.total_seconds())

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinator.client is mock_client
    assert entry.runtime_data.local_coordinator is not None
    assert hass.states.get(cover_entity_id).state != STATE_UNAVAILABLE
    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "local_error",
    [
        pytest.param(ClientError, id="cannot_connect"),
        pytest.param(NotAuthenticatedError, id="invalid_token"),
    ],
)
async def test_setup_without_local_api_sets_up_all_devices_through_the_cloud(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
    mock_local_client: MockOverkizClient,
    local_error: type[Exception],
) -> None:
    """Test the cloud API handles all devices when the local API cannot be used."""
    mock_local_client.login.side_effect = local_error

    await _async_setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data
    assert data.coordinator.client is mock_client
    assert data.local_coordinator is None
    assert COVER.device_url in data.coordinator.data
    assert hass.states.get(COVER.entity_id).state != STATE_UNAVAILABLE
    assert hass.states.get(POOL_PUMP.entity_id).state != STATE_UNAVAILABLE

    # The local devices move to the local API as soon as it can be used
    mock_local_client.login.side_effect = None
    await _async_pass_time(hass, freezer, API_RETRY_INTERVAL.total_seconds())

    assert entry.state is ConfigEntryState.LOADED
    assert "Local API can be used again" in caplog.text
    assert list(entry.runtime_data.local_coordinator.data) == [COVER.device_url]
    assert hass.states.get(COVER.entity_id).state != STATE_UNAVAILABLE


async def test_setup_with_failing_local_refresh_sets_up_all_devices_through_the_cloud(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
    mock_local_client: MockOverkizClient,
) -> None:
    """Test the cloud API handles all devices when the local API has no events."""
    mock_local_client.fetch_events.side_effect = TimeoutError

    await _async_setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data
    assert data.coordinator.client is mock_client
    assert data.local_coordinator is None
    assert COVER.device_url in data.coordinator.data
    assert hass.states.get(COVER.entity_id).state != STATE_UNAVAILABLE


async def test_setup_with_failing_cloud_refresh_sets_up_local_devices(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
    mock_local_client: MockOverkizClient,
) -> None:
    """Test the local devices are set up when the cloud API has no events."""
    mock_client.fetch_events.side_effect = TimeoutError

    await _async_setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data
    assert data.coordinator.client is mock_local_client
    assert data.local_coordinator is None
    assert list(data.coordinator.data) == [COVER.device_url]
    assert hass.states.get(COVER.entity_id).state != STATE_UNAVAILABLE


async def test_rejected_cloud_credentials_after_setup_without_cloud_start_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
) -> None:
    """Test the retry of the cloud API does not hide rejected credentials."""
    mock_client.login.side_effect = ClientError
    await _async_setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    mock_client.login.side_effect = BadCredentialsError
    await _async_pass_time(hass, freezer, API_RETRY_INTERVAL.total_seconds())

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1


async def test_rejected_local_token_after_setup_without_local_api_keeps_the_cloud(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    mock_local_client: MockOverkizClient,
) -> None:
    """Test the entry is not reloaded for a local API that rejects the token."""
    mock_local_client.login.side_effect = ClientError
    await _async_setup(hass, entry)
    data = entry.runtime_data

    mock_local_client.login.side_effect = NotAuthenticatedError
    await _async_pass_time(hass, freezer, API_RETRY_INTERVAL.total_seconds())

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is data
    assert hass.states.get(COVER.entity_id).state != STATE_UNAVAILABLE


async def test_setup_is_retried_when_no_api_can_be_reached(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
    mock_local_client: MockOverkizClient,
) -> None:
    """Test the entry is not set up when neither API can be reached."""
    mock_client.login.side_effect = ClientError
    mock_local_client.login.side_effect = ClientError

    await _async_setup(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_with_rejected_cloud_credentials_starts_reauth(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
    mock_local_client: MockOverkizClient,
) -> None:
    """Test the local API does not hide that the cloud credentials are rejected."""
    mock_client.login.side_effect = BadCredentialsError

    await _async_setup(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_local_client.login.await_count == 0
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1


async def test_setup_without_local_api_only_uses_the_cloud(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MockOverkizClient,
    mock_local_client: MockOverkizClient,
) -> None:
    """Test an entry without local API is set up through the cloud API alone."""
    mock_config_entry.add_to_hass(hass)

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    data = mock_config_entry.runtime_data
    assert data.coordinator.client is mock_client
    assert data.local_coordinator is None
    assert len(data.devices) == len(load_setup_fixture(FIXTURE).devices)
    assert mock_local_client.login.await_count == 0


async def test_unload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test unloading an entry that uses both APIs."""
    await _async_setup(hass, entry)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(COVER.entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get(POOL_PUMP.entity_id).state == STATE_UNAVAILABLE


async def test_retry_stops_when_the_entry_is_unloaded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    mock_client: MockOverkizClient,
) -> None:
    """Test an unloaded entry no longer tries the API that was missing."""
    mock_client.login = AsyncMock(side_effect=ClientError)
    await _async_setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    attempts = mock_client.login.await_count

    await _async_pass_time(hass, freezer, API_RETRY_INTERVAL.total_seconds())

    assert mock_client.login.await_count == attempts
    assert entry.state is ConfigEntryState.NOT_LOADED
