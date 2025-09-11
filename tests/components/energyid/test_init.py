"""Test EnergyID integration init with comprehensive coverage."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.energyid import (
    EnergyIDRuntimeData,
    _async_handle_state_change,
    async_config_entry_update_listener,
    async_setup_entry,
    async_unload_entry,
    async_update_listeners,
)
from homeassistant.components.energyid.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_UUID,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_webhook_client():
    """Create a mock WebhookClient."""
    client = MagicMock()
    client.authenticate = AsyncMock(return_value=True)
    client.device_name = "Test Device"
    client.webhook_policy = {"uploadInterval": 30}
    client.start_auto_sync = MagicMock()
    client.get_or_create_sensor = MagicMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PROVISIONING_KEY: "test_key",
            CONF_PROVISIONING_SECRET: "test_secret",
            CONF_DEVICE_ID: "test_device",
            CONF_DEVICE_NAME: "Test Device",
        },
        entry_id="test_entry",
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)
    return entry


def create_subentry(
    hass: HomeAssistant,
    parent_entry: MockConfigEntry,
    data: dict,
    entry_id: str = "sub_entry",
) -> MockConfigEntry:
    """Create a mock subentry and link it to the parent for testing."""
    # Patch subentries with a mutable dict for test purposes
    # If subentries is a mappingproxy, replace it with a mutable dict
    if not hasattr(parent_entry, "subentries") or not isinstance(
        parent_entry.subentries, dict
    ):
        # Patch the attribute directly (MockConfigEntry allows this)
        parent_entry.subentries = {}
    subentry = MagicMock()
    subentry.data = data
    subentry.entry_id = entry_id
    parent_entry.subentries[entry_id] = subentry
    return subentry


async def test_async_setup_entry_success_claimed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test successful setup when device is claimed."""
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        result = await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()

        assert result is True
        assert hasattr(mock_config_entry, "runtime_data")
        assert mock_config_entry.runtime_data.client == mock_webhook_client
        mock_webhook_client.authenticate.assert_called_once()
    # start_auto_sync is no longer called; background sync is managed by the integration


async def test_async_setup_entry_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup with timeout error."""
    mock_webhook_client.authenticate.side_effect = TimeoutError("Timeout")

    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client,
        ),
        pytest.raises(
            ConfigEntryNotReady, match="Timeout authenticating with EnergyID"
        ),
    ):
        await async_setup_entry(hass, mock_config_entry)


async def test_async_setup_entry_unexpected_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup with unexpected error during authentication."""
    mock_webhook_client.authenticate.side_effect = Exception("Unexpected")

    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client,
        ),
        pytest.raises(
            ConfigEntryAuthFailed, match="Failed to authenticate with EnergyID"
        ),
    ):
        await async_setup_entry(hass, mock_config_entry)


async def test_async_setup_entry_not_claimed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup when device is not claimed."""
    mock_webhook_client.authenticate.return_value = False

    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client,
        ),
        pytest.raises(Exception) as exc_info,
    ):
        await async_setup_entry(hass, mock_config_entry)
    # The new code raises ConfigEntryAuthFailed, which is a subclass of HomeAssistantError
    # and not ConfigEntryError. Check the message for clarity.
    assert "Device is not claimed" in str(exc_info.value)


async def test_async_setup_entry_default_upload_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup uses default upload interval when not in webhook_policy."""
    mock_webhook_client.webhook_policy = {}

    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        result = await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()

        assert result is True
    # start_auto_sync is no longer called; background sync is managed by the integration


async def test_async_setup_entry_no_webhook_policy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup when webhook_policy is None."""
    mock_webhook_client.webhook_policy = None

    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        result = await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()

        assert result is True
    # start_auto_sync is no longer called; background sync is managed by the integration


async def test_async_update_listeners(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners function for a valid mapping."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "power_1", suggested_object_id="power_meter"
    )
    hass.states.async_set("sensor.power_meter", "100")

    create_subentry(
        hass,
        mock_config_entry,
        data={CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "power"},
    )
    await hass.async_block_till_done()

    mock_sensor = MagicMock()
    mock_webhook_client.get_or_create_sensor.return_value = mock_sensor

    await async_update_listeners(hass, mock_config_entry)

    assert "sensor.power_meter" in mock_config_entry.runtime_data.mappings
    assert mock_config_entry.runtime_data.mappings["sensor.power_meter"] == "power"
    mock_webhook_client.get_or_create_sensor.assert_called_with("power")
    mock_sensor.update.assert_called_once()


async def test_async_update_listeners_entity_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners when entity UUID doesn't exist."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    create_subentry(
        hass,
        mock_config_entry,
        data={
            CONF_HA_ENTITY_UUID: "non-existent-uuid",
            CONF_ENERGYID_KEY: "power",
        },
    )
    await hass.async_block_till_done()

    await async_update_listeners(hass, mock_config_entry)

    assert not mock_config_entry.runtime_data.mappings
    mock_webhook_client.get_or_create_sensor.assert_not_called()


async def test_async_update_listeners_entity_no_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners when entity has no state."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "no_state", suggested_object_id="no_state_meter"
    )
    create_subentry(
        hass,
        mock_config_entry,
        data={CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "power"},
    )
    await hass.async_block_till_done()

    await async_update_listeners(hass, mock_config_entry)

    assert not mock_config_entry.runtime_data.mappings


async def test_async_update_listeners_invalid_subentry_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners with invalid subentry data (missing keys)."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    create_subentry(hass, mock_config_entry, data={})
    await hass.async_block_till_done()

    await async_update_listeners(hass, mock_config_entry)

    assert not mock_config_entry.runtime_data.mappings


async def test_async_update_listeners_removes_old_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test that async_update_listeners removes the old state listener."""
    old_listener = MagicMock()
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client,
        listeners={"state_listener": old_listener},
        mappings={},
    )

    await async_update_listeners(hass, mock_config_entry)

    old_listener.assert_called_once()
    assert "state_listener" not in mock_config_entry.runtime_data.listeners


async def test_async_update_listeners_logs_removed_mappings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test that async_update_listeners correctly handles removed mappings."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client,
        listeners={},
        mappings={"sensor.old_meter": "old_power"},
    )
    # No subentries are created, so the old mapping should be detected as removed.
    await async_update_listeners(hass, mock_config_entry)
    assert not mock_config_entry.runtime_data.mappings


async def test_async_update_listeners_no_valid_mappings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners when no valid mappings are configured."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    await async_update_listeners(hass, mock_config_entry)
    assert not mock_config_entry.runtime_data.listeners


async def test_async_update_listeners_non_numeric_initial_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners with a non-numeric initial state."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "text_1", suggested_object_id="text_meter"
    )
    hass.states.async_set("sensor.text_meter", "not_a_number")
    create_subentry(
        hass,
        mock_config_entry,
        data={CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "text"},
    )
    await hass.async_block_till_done()

    mock_sensor = MagicMock()
    mock_webhook_client.get_or_create_sensor.return_value = mock_sensor
    await async_update_listeners(hass, mock_config_entry)

    assert "sensor.text_meter" in mock_config_entry.runtime_data.mappings
    mock_sensor.update.assert_not_called()


async def test_async_update_listeners_unknown_unavailable_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners with unknown/unavailable initial states."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    entity1 = entity_registry.async_get_or_create(
        "sensor", "test", "unknown_1", suggested_object_id="unknown_meter"
    )
    hass.states.async_set("sensor.unknown_meter", STATE_UNKNOWN)
    create_subentry(
        hass,
        mock_config_entry,
        data={CONF_HA_ENTITY_UUID: entity1.id, CONF_ENERGYID_KEY: "unknown"},
        entry_id="sub1",
    )

    entity2 = entity_registry.async_get_or_create(
        "sensor", "test", "unavail_1", suggested_object_id="unavailable_meter"
    )
    hass.states.async_set("sensor.unavailable_meter", STATE_UNAVAILABLE)
    create_subentry(
        hass,
        mock_config_entry,
        data={CONF_HA_ENTITY_UUID: entity2.id, CONF_ENERGYID_KEY: "unavailable"},
        entry_id="sub2",
    )
    await hass.async_block_till_done()

    mock_sensor = MagicMock()
    mock_webhook_client.get_or_create_sensor.return_value = mock_sensor
    await async_update_listeners(hass, mock_config_entry)

    assert "sensor.unknown_meter" in mock_config_entry.runtime_data.mappings
    assert "sensor.unavailable_meter" in mock_config_entry.runtime_data.mappings
    mock_sensor.update.assert_not_called()


async def test_async_update_listeners_with_existing_mappings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners with existing mappings (no initial state queue)."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client,
        listeners={},
        mappings={"sensor.power_meter": "power"},
    )

    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "power_1", suggested_object_id="power_meter"
    )
    hass.states.async_set("sensor.power_meter", "100")

    create_subentry(
        hass,
        mock_config_entry,
        data={CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "power"},
    )
    await hass.async_block_till_done()

    mock_sensor = MagicMock()
    mock_webhook_client.get_or_create_sensor.return_value = mock_sensor

    await async_update_listeners(hass, mock_config_entry)

    assert "sensor.power_meter" in mock_config_entry.runtime_data.mappings
    mock_sensor.update.assert_not_called()


async def test_async_update_listeners_state_with_none_timestamp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners with a state that has no last_updated timestamp."""

    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "ts_1", suggested_object_id="timestamp_meter"
    )

    state_with_no_timestamp = State("sensor.timestamp_meter", "100")
    state_with_no_timestamp.last_updated = None
    hass.states.async_set("sensor.timestamp_meter", "100")
    hass.states._states["sensor.timestamp_meter"] = state_with_no_timestamp

    create_subentry(
        hass,
        mock_config_entry,
        data={
            CONF_HA_ENTITY_UUID: entity_entry.id,
            CONF_ENERGYID_KEY: "timestamp_test",
        },
    )
    await hass.async_block_till_done()

    mock_sensor = MagicMock()
    mock_webhook_client.get_or_create_sensor.return_value = mock_sensor

    with patch("homeassistant.components.energyid.dt.datetime") as mock_dt:
        mock_now = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
        mock_dt.now.return_value = mock_now

        await async_update_listeners(hass, mock_config_entry)

    assert "sensor.timestamp_meter" in mock_config_entry.runtime_data.mappings
    mock_sensor.update.assert_called_once_with(100.0, mock_now)


async def test_async_config_entry_update_listener(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry update listener schedules the correct callback."""
    with patch(
        "homeassistant.components.energyid.async_update_listeners"
    ) as mock_update:
        await async_config_entry_update_listener(hass, mock_config_entry)
        mock_update.assert_called_once_with(hass, mock_config_entry)


async def test_async_unload_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test successful unload of a config entry."""
    mock_listener = MagicMock()
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client,
        listeners={"test_listener": mock_listener},
        mappings={},
    )

    result = await async_unload_entry(hass, mock_config_entry)

    assert result is True
    mock_listener.cancel.assert_called_once()
    mock_webhook_client.close.assert_called_once()


async def test_async_unload_entry_no_runtime_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unload when entry has no runtime_data."""
    if hasattr(mock_config_entry, "runtime_data"):
        delattr(mock_config_entry, "runtime_data")
    result = await async_unload_entry(hass, mock_config_entry)
    assert result is True


async def test_async_unload_entry_client_close_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test unload when client.close() raises an exception."""
    mock_webhook_client.close.side_effect = Exception("Close error")
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    assert await async_unload_entry(hass, mock_config_entry) is True


async def test_async_unload_entry_general_exception(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unload when a general exception occurs."""
    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.listeners.values.side_effect = Exception(
        "General error"
    )
    assert await async_unload_entry(hass, mock_config_entry) is False


def test_state_change_handler_numeric_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the state change handler with a valid numeric state."""
    mock_sensor = MagicMock()
    mock_webhook_client.get_or_create_sensor.return_value = mock_sensor
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client,
        listeners={},
        mappings={"sensor.power_meter": "power"},
    )
    mock_state = MagicMock(state="100.5", last_updated="2023-01-01T00:00:00Z")
    event = Event(
        "state_changed",
        {"entity_id": "sensor.power_meter", "new_state": mock_state},
    )

    _async_handle_state_change(hass, mock_config_entry.entry_id, event)

    mock_webhook_client.get_or_create_sensor.assert_called_with("power")
    mock_sensor.update.assert_called_once_with(100.5, mock_state.last_updated)


def test_state_change_handler_non_numeric_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the state change handler with a non-numeric state."""
    mock_sensor = MagicMock()
    mock_webhook_client.get_or_create_sensor.return_value = mock_sensor
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client,
        listeners={},
        mappings={"sensor.text_meter": "text"},
    )
    mock_state = MagicMock(state="not_a_number")
    event = Event(
        "state_changed", {"entity_id": "sensor.text_meter", "new_state": mock_state}
    )

    _async_handle_state_change(hass, mock_config_entry.entry_id, event)

    mock_sensor.update.assert_not_called()


def test_state_change_handler_type_error_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the state change handler with a state that causes TypeError."""
    mock_sensor = MagicMock()
    mock_webhook_client.get_or_create_sensor.return_value = mock_sensor
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client,
        listeners={},
        mappings={"sensor.type_error_meter": "type_error"},
    )
    mock_state = MagicMock(state=None)
    event = Event(
        "state_changed",
        {"entity_id": "sensor.type_error_meter", "new_state": mock_state},
    )

    _async_handle_state_change(hass, mock_config_entry.entry_id, event)

    mock_sensor.update.assert_not_called()


def test_state_change_handler_removed_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the state change handler when an entity is removed (new_state is None)."""
    event = Event("state_changed", {"entity_id": "sensor.removed", "new_state": None})
    _async_handle_state_change(hass, mock_config_entry.entry_id, event)


def test_state_change_handler_unavailable_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the state change handler with an unavailable state."""
    mock_state = MagicMock(state=STATE_UNAVAILABLE)
    event = Event(
        "state_changed",
        {"entity_id": "sensor.unavailable_meter", "new_state": mock_state},
    )
    _async_handle_state_change(hass, mock_config_entry.entry_id, event)


def test_state_change_handler_unknown_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the state change handler with an unknown state."""
    mock_state = MagicMock(state=STATE_UNKNOWN)
    event = Event(
        "state_changed",
        {"entity_id": "sensor.unknown_meter", "new_state": mock_state},
    )
    _async_handle_state_change(hass, mock_config_entry.entry_id, event)


def test_state_change_handler_entry_not_found(hass: HomeAssistant) -> None:
    """Test the state change handler when the config entry is not found."""
    mock_state = MagicMock(state="100")
    event = Event(
        "state_changed",
        {"entity_id": "sensor.power_meter", "new_state": mock_state},
    )
    _async_handle_state_change(hass, "non_existent_entry", event)


def test_state_change_handler_entry_no_runtime_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the state change handler when the entry has no runtime_data."""
    if hasattr(mock_config_entry, "runtime_data"):
        delattr(mock_config_entry, "runtime_data")
    mock_state = MagicMock(state="100")
    event = Event(
        "state_changed",
        {"entity_id": "sensor.power_meter", "new_state": mock_state},
    )
    _async_handle_state_change(hass, mock_config_entry.entry_id, event)


def test_state_change_handler_unmapped_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the state change handler for an unmapped entity."""
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )
    mock_state = MagicMock(state="100")
    event = Event(
        "state_changed",
        {"entity_id": "sensor.unmapped_meter", "new_state": mock_state},
    )

    _async_handle_state_change(hass, mock_config_entry.entry_id, event)

    mock_webhook_client.get_or_create_sensor.assert_not_called()


async def test_async_unload_entry_with_subentries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test successful unload of a config entry that has subentries."""
    # Set up the parent entry
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client, listeners={}, mappings={}
    )

    # Create and link a subentry
    create_subentry(
        hass,
        mock_config_entry,
        data={"ha_entity_uuid": "some-uuid", "energyid_key": "some_key"},
    )
    await hass.async_block_till_done()

    # Even though subentries exist, they are not real config entries, so async_unload is not called.
    result = await async_unload_entry(hass, mock_config_entry)
    assert result is True
    mock_webhook_client.close.assert_called_once()
