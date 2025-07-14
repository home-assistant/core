"""Tests for the helper entity helpers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
    async_remove_helper_config_entry_from_source_device,
)

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

HELPER_DOMAIN = "helper"
SOURCE_DOMAIN = "test"


@pytest.fixture
def source_config_entry(hass: HomeAssistant) -> er.RegistryEntry:
    """Fixture to create a source config entry."""
    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)
    return source_config_entry


@pytest.fixture
def source_device(
    device_registry: dr.DeviceRegistry,
    source_config_entry: ConfigEntry,
) -> dr.DeviceEntry:
    """Fixture to create a source device."""
    return device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )


@pytest.fixture
def source_entity_entry(
    entity_registry: er.EntityRegistry,
    source_config_entry: ConfigEntry,
    source_device: dr.DeviceEntry,
) -> er.RegistryEntry:
    """Fixture to create a source entity entry."""
    return entity_registry.async_get_or_create(
        "sensor",
        SOURCE_DOMAIN,
        "unique",
        config_entry=source_config_entry,
        device_id=source_device.id,
        original_name="ABC",
    )


@pytest.fixture
def helper_config_entry(
    hass: HomeAssistant,
    source_entity_entry: er.RegistryEntry,
    use_entity_registry_id: bool,
) -> MockConfigEntry:
    """Fixture to create a helper config entry."""
    config_entry = MockConfigEntry(
        data={},
        domain=HELPER_DOMAIN,
        options={
            "name": "My helper",
            "round": 1.0,
            "source": source_entity_entry.id
            if use_entity_registry_id
            else source_entity_entry.entity_id,
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="My helper",
    )

    config_entry.add_to_hass(hass)

    return config_entry


@pytest.fixture
def mock_helper_flow() -> Generator[None]:
    """Mock helper config flow."""

    class MockConfigFlow:
        """Mock the helper config flow."""

        VERSION = 1
        MINOR_VERSION = 1

    with mock_config_flow(HELPER_DOMAIN, MockConfigFlow):
        yield


@pytest.fixture
def helper_entity_entry(
    entity_registry: er.EntityRegistry,
    helper_config_entry: ConfigEntry,
    source_device: dr.DeviceEntry,
) -> er.RegistryEntry:
    """Fixture to create a helper entity entry."""
    return entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        helper_config_entry.entry_id,
        config_entry=helper_config_entry,
        device_id=source_device.id,
        original_name="ABC",
    )


@pytest.fixture
def async_remove_entry() -> AsyncMock:
    """Fixture to mock async_remove_entry."""
    return AsyncMock(return_value=True)


@pytest.fixture
def async_unload_entry() -> AsyncMock:
    """Fixture to mock async_unload_entry."""
    return AsyncMock(return_value=True)


@pytest.fixture
def set_source_entity_id_or_uuid() -> Mock:
    """Fixture to mock set_source_entity_id_or_uuid."""
    return Mock()


@pytest.fixture
def source_entity_removed() -> AsyncMock:
    """Fixture to mock source_entity_removed."""
    return AsyncMock()


@pytest.fixture
def mock_helper_integration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    helper_config_entry: MockConfigEntry,
    source_entity_entry: er.RegistryEntry,
    async_remove_entry: AsyncMock,
    async_unload_entry: AsyncMock,
    set_source_entity_id_or_uuid: Mock,
    source_entity_removed: AsyncMock | None,
) -> None:
    """Mock the helper integration."""

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setup entry."""
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=helper_config_entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=source_entity_entry.device_id,
            source_entity_id_or_uuid=helper_config_entry.options["source"],
            source_entity_removed=source_entity_removed,
        )
        return True

    mock_integration(
        hass,
        MockModule(
            HELPER_DOMAIN,
            async_remove_entry=async_remove_entry,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, f"{HELPER_DOMAIN}.config_flow", None)


def track_entity_registry_actions(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Track entity registry actions for an entity."""
    events = []

    @callback
    def add_event(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Add entity registry updated event to the list."""
        events.append(event.data["action"])

    async_track_entity_registry_updated_event(hass, entity_id, add_event)

    return events


def listen_entity_registry_events(
    hass: HomeAssistant,
) -> list[er.EventEntityRegistryUpdatedData]:
    """Track entity registry actions for an entity."""
    events: list[er.EventEntityRegistryUpdatedData] = []

    @callback
    def add_event(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Add entity registry updated event to the list."""
        events.append(event.data)

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, add_event)

    return events


@pytest.mark.parametrize("source_entity_removed", [None])
@pytest.mark.parametrize("use_entity_registry_id", [True, False])
@pytest.mark.usefixtures("mock_helper_flow", "mock_helper_integration")
async def test_async_handle_source_entity_changes_source_entity_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_config_entry: MockConfigEntry,
    helper_entity_entry: er.RegistryEntry,
    source_config_entry: ConfigEntry,
    source_device: dr.DeviceEntry,
    source_entity_entry: er.RegistryEntry,
    async_remove_entry: AsyncMock,
    async_unload_entry: AsyncMock,
    set_source_entity_id_or_uuid: Mock,
) -> None:
    """Test the helper config entry is removed when the source entity is removed."""
    # Add the helper config entry to the source device
    device_registry.async_update_device(
        source_device.id, add_config_entry_id=helper_config_entry.entry_id
    )
    # Add another config entry to the source device
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry.async_update_device(
        source_device.id, add_config_entry_id=other_config_entry.entry_id
    )

    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id
    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id in source_device.config_entries

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Remove the source entitys's config entry from the device, this removes the
    # source entity
    device_registry.async_update_device(
        source_device.id, remove_config_entry_id=source_config_entry.entry_id
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Check that the helper entity is not linked to the source device anymore
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id is None
    async_unload_entry.assert_not_called()
    async_remove_entry.assert_not_called()
    set_source_entity_id_or_uuid.assert_not_called()

    # Check that the helper config entry is not removed from the device
    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id in source_device.config_entries

    # Check that the helper config entry is not removed
    assert helper_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


@pytest.mark.parametrize("use_entity_registry_id", [True, False])
@pytest.mark.usefixtures("mock_helper_flow", "mock_helper_integration")
async def test_async_handle_source_entity_changes_source_entity_removed_custom_handler(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_config_entry: MockConfigEntry,
    helper_entity_entry: er.RegistryEntry,
    source_config_entry: ConfigEntry,
    source_device: dr.DeviceEntry,
    source_entity_entry: er.RegistryEntry,
    async_remove_entry: AsyncMock,
    async_unload_entry: AsyncMock,
    set_source_entity_id_or_uuid: Mock,
    source_entity_removed: AsyncMock,
) -> None:
    """Test the helper config entry is removed when the source entity is removed."""
    # Add the helper config entry to the source device
    device_registry.async_update_device(
        source_device.id, add_config_entry_id=helper_config_entry.entry_id
    )
    # Add another config entry to the source device
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry.async_update_device(
        source_device.id, add_config_entry_id=other_config_entry.entry_id
    )

    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id
    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id in source_device.config_entries

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Remove the source entitys's config entry from the device, this removes the
    # source entity
    device_registry.async_update_device(
        source_device.id, remove_config_entry_id=source_config_entry.entry_id
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Check that the source_entity_removed callback was called
    source_entity_removed.assert_called_once()
    async_unload_entry.assert_not_called()
    async_remove_entry.assert_not_called()
    set_source_entity_id_or_uuid.assert_not_called()

    # Check that the helper config entry is not removed from the device
    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id in source_device.config_entries

    # Check that the helper config entry is not removed
    assert helper_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == []


@pytest.mark.parametrize("use_entity_registry_id", [True, False])
@pytest.mark.usefixtures("mock_helper_flow", "mock_helper_integration")
async def test_async_handle_source_entity_changes_source_entity_removed_from_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_config_entry: MockConfigEntry,
    helper_entity_entry: er.RegistryEntry,
    source_device: dr.DeviceEntry,
    source_entity_entry: er.RegistryEntry,
    async_remove_entry: AsyncMock,
    async_unload_entry: AsyncMock,
    set_source_entity_id_or_uuid: Mock,
) -> None:
    """Test the source entity removed from the source device."""
    # Add the helper config entry to the source device
    device_registry.async_update_device(
        source_device.id, add_config_entry_id=helper_config_entry.entry_id
    )

    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id

    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id in source_device.config_entries

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Remove the source entity from the device
    entity_registry.async_update_entity(source_entity_entry.entity_id, device_id=None)
    await hass.async_block_till_done()
    async_remove_entry.assert_not_called()
    async_unload_entry.assert_called_once()
    set_source_entity_id_or_uuid.assert_not_called()

    # Check that the helper config entry is removed from the device
    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id not in source_device.config_entries

    # Check that the helper config entry is not removed
    assert helper_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


@pytest.mark.parametrize("use_entity_registry_id", [True, False])
@pytest.mark.usefixtures("mock_helper_flow", "mock_helper_integration")
async def test_async_handle_source_entity_changes_source_entity_moved_other_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_config_entry: MockConfigEntry,
    helper_entity_entry: er.RegistryEntry,
    source_config_entry: ConfigEntry,
    source_device: dr.DeviceEntry,
    source_entity_entry: er.RegistryEntry,
    async_remove_entry: AsyncMock,
    async_unload_entry: AsyncMock,
    set_source_entity_id_or_uuid: Mock,
) -> None:
    """Test the source entity is moved to another device."""
    # Add the helper config entry to the source device
    device_registry.async_update_device(
        source_device.id, add_config_entry_id=helper_config_entry.entry_id
    )

    # Create another device to move the source entity to
    source_device_2 = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
    )

    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id

    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id in source_device.config_entries
    source_device_2 = device_registry.async_get(source_device_2.id)
    assert helper_config_entry.entry_id not in source_device_2.config_entries

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Move the source entity to another device
    entity_registry.async_update_entity(
        source_entity_entry.entity_id, device_id=source_device_2.id
    )
    await hass.async_block_till_done()
    async_remove_entry.assert_not_called()
    async_unload_entry.assert_called_once()
    set_source_entity_id_or_uuid.assert_not_called()

    # Check that the helper config entry is moved to the other device
    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id not in source_device.config_entries
    source_device_2 = device_registry.async_get(source_device_2.id)
    assert helper_config_entry.entry_id in source_device_2.config_entries

    # Check that the helper config entry is not removed
    assert helper_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


@pytest.mark.parametrize(
    ("use_entity_registry_id", "unload_calls", "set_source_entity_id_calls"),
    [(True, 1, 0), (False, 0, 1)],
)
@pytest.mark.usefixtures("mock_helper_flow", "mock_helper_integration")
async def test_async_handle_source_entity_new_entity_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_config_entry: MockConfigEntry,
    helper_entity_entry: er.RegistryEntry,
    source_device: dr.DeviceEntry,
    source_entity_entry: er.RegistryEntry,
    async_remove_entry: AsyncMock,
    async_unload_entry: AsyncMock,
    set_source_entity_id_or_uuid: Mock,
    unload_calls: int,
    set_source_entity_id_calls: int,
) -> None:
    """Test the source entity's entity ID is changed."""
    # Add the helper config entry to the source device
    device_registry.async_update_device(
        source_device.id, add_config_entry_id=helper_config_entry.entry_id
    )

    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id

    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id in source_device.config_entries

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Change the source entity's entity ID
    entity_registry.async_update_entity(
        source_entity_entry.entity_id, new_entity_id="sensor.new_entity_id"
    )
    await hass.async_block_till_done()
    async_remove_entry.assert_not_called()
    assert len(async_unload_entry.mock_calls) == unload_calls
    assert len(set_source_entity_id_or_uuid.mock_calls) == set_source_entity_id_calls

    # Check that the helper config is still in the device
    source_device = device_registry.async_get(source_device.id)
    assert helper_config_entry.entry_id in source_device.config_entries

    # Check that the helper config entry is not removed
    assert helper_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == []


@pytest.mark.parametrize("use_entity_registry_id", [True, False])
@pytest.mark.usefixtures("source_entity_entry")
async def test_async_remove_helper_config_entry_from_source_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_config_entry: MockConfigEntry,
    helper_entity_entry: er.RegistryEntry,
    source_device: dr.DeviceEntry,
) -> None:
    """Test removing the helper config entry from the source device."""
    # Add the helper config entry to the source device
    device_registry.async_update_device(
        source_device.id, add_config_entry_id=helper_config_entry.entry_id
    )

    # Create a helper entity entry, not connected to the source device
    extra_helper_entity_entry = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        f"{helper_config_entry.entry_id}_2",
        config_entry=helper_config_entry,
        original_name="ABC",
    )
    assert extra_helper_entity_entry.entity_id != helper_entity_entry.entity_id

    events = listen_entity_registry_events(hass)

    async_remove_helper_config_entry_from_source_device(
        hass,
        helper_config_entry_id=helper_config_entry.entry_id,
        source_device_id=source_device.id,
    )

    # Check we got the expected events
    assert events == [
        {
            "action": "update",
            "changes": {"device_id": source_device.id},
            "entity_id": helper_entity_entry.entity_id,
        },
        {
            "action": "update",
            "changes": {"device_id": None},
            "entity_id": helper_entity_entry.entity_id,
        },
    ]


@pytest.mark.parametrize("use_entity_registry_id", [True, False])
@pytest.mark.usefixtures("source_entity_entry")
async def test_async_remove_helper_config_entry_from_source_device_helper_not_in_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_config_entry: MockConfigEntry,
    helper_entity_entry: er.RegistryEntry,
    source_device: dr.DeviceEntry,
) -> None:
    """Test removing the helper config entry from the source device."""
    # Create a helper entity entry, not connected to the source device
    extra_helper_entity_entry = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        f"{helper_config_entry.entry_id}_2",
        config_entry=helper_config_entry,
        original_name="ABC",
    )
    assert extra_helper_entity_entry.entity_id != helper_entity_entry.entity_id

    events = listen_entity_registry_events(hass)

    async_remove_helper_config_entry_from_source_device(
        hass,
        helper_config_entry_id=helper_config_entry.entry_id,
        source_device_id=source_device.id,
    )

    # Check we got the expected events
    assert events == []
