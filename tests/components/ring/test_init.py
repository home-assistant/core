"""The tests for the Ring component."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from ring_doorbell import AuthenticationError, Ring, RingError, RingTimeout

from homeassistant.components import ring
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.ring import DOMAIN
from homeassistant.components.ring.const import CONF_LISTEN_CREDENTIALS, SCAN_INTERVAL
from homeassistant.components.ring.coordinator import RingEventListener
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HARDWARE_ID
from .device_mocks import FRONT_DOOR_DEVICE_ID

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup(hass: HomeAssistant, mock_ring_client) -> None:
    """Test the setup."""
    await async_setup_component(hass, ring.DOMAIN, {})


async def test_setup_entry(
    hass: HomeAssistant,
    mock_ring_client,
    mock_added_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry."""
    assert mock_added_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_device_update(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    freezer: FrozenDateTimeFactory,
    mock_added_config_entry: MockConfigEntry,
) -> None:
    """Test devices are updating after setup entry."""

    front_door_doorbell = mock_ring_devices.get_device(987654)
    front_door_doorbell.async_history.assert_not_called()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    front_door_doorbell.async_history.assert_called_once()


async def test_auth_failed_on_setup(
    hass: HomeAssistant,
    mock_ring_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test auth failure on setup entry."""
    mock_config_entry.add_to_hass(hass)
    mock_ring_client.async_update_data.side_effect = AuthenticationError

    assert not any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("error_type", "log_msg"),
    [
        (
            RingTimeout,
            "Timeout communicating with API: ",
        ),
        (
            RingError,
            "Error communicating with API: ",
        ),
    ],
    ids=["timeout-error", "other-error"],
)
async def test_error_on_setup(
    hass: HomeAssistant,
    mock_ring_client,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    error_type,
    log_msg,
) -> None:
    """Test non-auth errors on setup entry."""
    mock_config_entry.add_to_hass(hass)

    mock_ring_client.async_update_data.side_effect = error_type

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    assert log_msg in caplog.text


async def test_auth_failure_on_global_update(
    hass: HomeAssistant,
    mock_ring_client,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test authentication failure on global data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))

    mock_ring_client.async_update_devices.side_effect = AuthenticationError

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "Authentication failed while fetching devices data: " in caplog.text

    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_auth_failure_on_device_update(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test authentication failure on device data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))

    front_door_doorbell = mock_ring_devices.get_device(987654)
    front_door_doorbell.async_history.side_effect = AuthenticationError

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Authentication failed while fetching devices data: " in caplog.text

    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    ("error_type", "log_msg"),
    [
        (
            RingTimeout,
            "Error fetching devices data: Timeout communicating with API: ",
        ),
        (
            RingError,
            "Error fetching devices data: Error communicating with API: ",
        ),
    ],
    ids=["timeout-error", "other-error"],
)
async def test_error_on_global_update(
    hass: HomeAssistant,
    mock_ring_client,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    error_type,
    log_msg,
) -> None:
    """Test non-auth errors on global data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_ring_client.async_update_devices.side_effect = error_type

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert log_msg in caplog.text

    assert hass.config_entries.async_get_entry(mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("error_type", "log_msg"),
    [
        (
            RingTimeout,
            "Error fetching devices data: Timeout communicating with API for device Front: ",
        ),
        (
            RingError,
            "Error fetching devices data: Error communicating with API for device Front: ",
        ),
    ],
    ids=["timeout-error", "other-error"],
)
async def test_error_on_device_update(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    error_type,
    log_msg,
) -> None:
    """Test non-auth errors on device update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    front_door_doorbell = mock_ring_devices.get_device(765432)
    front_door_doorbell.async_history.side_effect = error_type

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert log_msg in caplog.text
    assert hass.config_entries.async_get_entry(mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("domain", "old_unique_id"),
    [
        (
            LIGHT_DOMAIN,
            123456,
        ),
        (
            CAMERA_DOMAIN,
            654321,
        ),
    ],
)
async def test_update_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    mock_ring_client,
    domain: str,
    old_unique_id: int | str,
) -> None:
    """Test unique_id update of integration."""
    entry = MockConfigEntry(
        title="Ring",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "foo@bar.com",
            "token": {"access_token": "mock-token"},
        },
        unique_id="foo@bar.com",
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        domain=domain,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == str(old_unique_id)
    assert (f"Fixing non string unique id {old_unique_id}") in caplog.text


async def test_update_unique_id_existing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    mock_ring_client,
) -> None:
    """Test unique_id update of integration."""
    old_unique_id = 123456
    entry = MockConfigEntry(
        title="Ring",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "foo@bar.com",
            "token": {"access_token": "mock-token"},
        },
        unique_id="foo@bar.com",
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        domain=CAMERA_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    entity_existing = entity_registry.async_get_or_create(
        domain=CAMERA_DOMAIN,
        platform=DOMAIN,
        unique_id=str(old_unique_id),
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id
    assert entity_existing.unique_id == str(old_unique_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_not_migrated = entity_registry.async_get(entity.entity_id)
    entity_existing = entity_registry.async_get(entity_existing.entity_id)
    assert entity_not_migrated
    assert entity_existing
    assert entity_not_migrated.unique_id == old_unique_id
    assert (
        f"Cannot migrate to unique_id '{old_unique_id}', "
        f"already exists for '{entity_existing.entity_id}', "
        "You may have to delete unavailable ring entities"
    ) in caplog.text


async def test_update_unique_id_no_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    mock_ring_client,
) -> None:
    """Test unique_id update of integration."""
    correct_unique_id = "123456"
    entry = MockConfigEntry(
        title="Ring",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "foo@bar.com",
            "token": {"access_token": "mock-token"},
        },
        unique_id="foo@bar.com",
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        domain=CAMERA_DOMAIN,
        platform=DOMAIN,
        unique_id="123456",
        config_entry=entry,
    )
    assert entity.unique_id == correct_unique_id
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == correct_unique_id
    assert "Fixing non string unique id" not in caplog.text


async def test_token_updated(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_ring_client,
    mock_ring_init_auth_class,
) -> None:
    """Test that the token value is updated in the config entry.

    This simulates the api calling the callback.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_ring_init_auth_class.call_count == 1
    token_updater = mock_ring_init_auth_class.call_args.args[2]
    assert mock_config_entry.data[CONF_TOKEN] == {"access_token": "mock-token"}

    mock_ring_client.async_update_devices.side_effect = lambda: token_updater(
        {"access_token": "new-mock-token"}
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_config_entry.data[CONF_TOKEN] == {"access_token": "new-mock-token"}


async def test_listen_token_updated(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_ring_client,
    mock_ring_event_listener_class,
) -> None:
    """Test that the listener token value is updated in the config entry.

    This simulates the api calling the callback.
    """
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_ring_event_listener_class.call_count == 1
    token_updater = mock_ring_event_listener_class.call_args.args[2]

    assert mock_config_entry.data.get(CONF_LISTEN_CREDENTIALS) is None
    token_updater({"listen_access_token": "mock-token"})
    assert mock_config_entry.data.get(CONF_LISTEN_CREDENTIALS) == {
        "listen_access_token": "mock-token"
    }


async def test_no_listen_start(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_registry: er.EntityRegistry,
    mock_ring_event_listener_class: type[RingEventListener],
    mock_ring_client: Ring,
) -> None:
    """Test behaviour if listener doesn't start."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={"username": "foo", "token": {}},
    )
    # Create a binary sensor entity so it is not ignored by the deprecation check
    # and the listener will start
    entity_registry.async_get_or_create(
        domain=BINARY_SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=f"{FRONT_DOOR_DEVICE_ID}-motion",
        suggested_object_id=f"{FRONT_DOOR_DEVICE_ID}_motion",
        config_entry=mock_entry,
    )
    mock_ring_event_listener_class.do_not_start = True

    mock_ring_event_listener_class.return_value.started = False

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert "Ring event listener failed to start after 10 seconds" in [
        record.message for record in caplog.records if record.levelname == "WARNING"
    ]


async def test_migrate_create_device_id(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test migration creates new device id created."""
    entry = MockConfigEntry(
        title="Ring",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "foo@bar.com",
            "token": {"access_token": "mock-token"},
        },
        unique_id="foo@bar.com",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    with patch("uuid.uuid4", return_value=MOCK_HARDWARE_ID):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert CONF_DEVICE_ID in entry.data
    assert entry.data[CONF_DEVICE_ID] == MOCK_HARDWARE_ID

    assert "Migration to version 1.2 complete" in caplog.text
