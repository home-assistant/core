"""Tests for the helper entity helpers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import attr
import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
    async_remove_helper_config_entry_from_source_device,
    async_remove_helper_devices,
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


@pytest.mark.parametrize("add_helper_config_entry_to_device", [True, False])
async def test_async_handle_source_entity_changes_deprecated_kwarg(
    hass: HomeAssistant,
    add_helper_config_entry_to_device: bool,
) -> None:
    """The removed add_helper_config_entry_to_device kwarg is accepted but reported.

    It is swallowed by **kwargs so callers still passing it don't raise, and reported on
    its presence rather than its value, since it no longer has any effect either way.
    """
    with patch("homeassistant.helpers.helper_integration.report_usage") as report_usage:
        unsub = async_handle_source_entity_changes(
            hass,
            helper_config_entry_id="helper_config_entry_id",
            set_source_entity_id_or_uuid=Mock(),
            source_device_id=None,
            source_entity_id_or_uuid="sensor.test",
            add_helper_config_entry_to_device=add_helper_config_entry_to_device,
        )
    unsub()

    report_usage.assert_called_once()
    assert "add_helper_config_entry_to_device" in report_usage.call_args[0][0]


async def test_async_handle_source_entity_changes_rejects_unknown_kwarg(
    hass: HomeAssistant,
) -> None:
    """An unknown keyword argument still raises, as it did before **kwargs was added.

    **kwargs only exists to swallow the deprecated add_helper_config_entry_to_device;
    anything else (e.g. a misspelling) must not be silently accepted.
    """
    with pytest.raises(TypeError, match="unexpected keyword arguments 'unknown_kwarg'"):
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id="helper_config_entry_id",
            set_source_entity_id_or_uuid=Mock(),
            source_device_id=None,
            source_entity_id_or_uuid="sensor.test",
            unknown_kwarg=True,
        )


async def test_async_handle_source_entity_changes_without_deprecated_kwarg(
    hass: HomeAssistant,
) -> None:
    """Not passing the removed add_helper_config_entry_to_device kwarg is not reported."""
    with patch("homeassistant.helpers.helper_integration.report_usage") as report_usage:
        unsub = async_handle_source_entity_changes(
            hass,
            helper_config_entry_id="helper_config_entry_id",
            set_source_entity_id_or_uuid=Mock(),
            source_device_id=None,
            source_entity_id_or_uuid="sensor.test",
        )
    unsub()

    report_usage.assert_not_called()


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
    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions - the helper entity is linked to the source device
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Remove the source entity
    entity_registry.async_remove(source_entity_entry.entity_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Check that the helper entity is not linked to the source device anymore
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id is None
    async_unload_entry.assert_not_called()
    async_remove_entry.assert_not_called()
    set_source_entity_id_or_uuid.assert_not_called()

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
    """Test the source_entity_removed handler is called when the source entity is removed."""
    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions - the helper entity is linked to the source device
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Remove the source entity
    entity_registry.async_remove(source_entity_entry.entity_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Check that the source_entity_removed callback was called
    source_entity_removed.assert_called_once()
    async_unload_entry.assert_not_called()
    async_remove_entry.assert_not_called()
    set_source_entity_id_or_uuid.assert_not_called()

    # Check that the custom handler took over: the helper entity is left linked to the
    # source device
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_device.id

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
    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions - the helper entity is linked to the source device
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Remove the source entity from the device
    entity_registry.async_update_entity(source_entity_entry.entity_id, device_id=None)
    await hass.async_block_till_done()
    async_remove_entry.assert_not_called()
    async_unload_entry.assert_called_once()
    set_source_entity_id_or_uuid.assert_not_called()

    # Check that the helper entity is not linked to the source device anymore
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id is None

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
    # Create another device to move the source entity to
    source_device_2 = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
    )

    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions - the helper entity is linked to the source device
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Move the source entity to another device
    entity_registry.async_update_entity(
        source_entity_entry.entity_id, device_id=source_device_2.id
    )
    await hass.async_block_till_done()
    async_remove_entry.assert_not_called()
    async_unload_entry.assert_called_once()
    set_source_entity_id_or_uuid.assert_not_called()

    # Check that the helper entity is relinked to the other device
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_device_2.id

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
    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check preconditions - the helper entity is linked to the source device
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_entity_entry.device_id

    events = track_entity_registry_actions(hass, helper_entity_entry.entity_id)

    # Change the source entity's entity ID
    entity_registry.async_update_entity(
        source_entity_entry.entity_id, new_entity_id="sensor.new_entity_id"
    )
    await hass.async_block_till_done()
    async_remove_entry.assert_not_called()
    assert len(async_unload_entry.mock_calls) == unload_calls
    assert len(set_source_entity_id_or_uuid.mock_calls) == set_source_entity_id_calls

    # Check that the helper entity is still linked to the source device
    helper_entity_entry = entity_registry.async_get(helper_entity_entry.entity_id)
    assert helper_entity_entry.device_id == source_device.id

    # Check that the helper config entry is not removed
    assert helper_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == []


@pytest.mark.parametrize(
    ("helper_identifiers", "helper_has_composite_identifiers"),
    [
        # Freshly split: the helper's split still carries the identifiers copied from the
        # co-owned device
        pytest.param({(SOURCE_DOMAIN, "1")}, True, id="not_activated"),
        # Activated: the helper re-registered its device, pruning it to its own identifiers
        pytest.param({(HELPER_DOMAIN, "1")}, False, id="activated"),
    ],
)
@pytest.mark.parametrize(
    "source_via_composite_id",
    [pytest.param(True, id="composite_id"), pytest.param(False, id="source_split")],
)
async def test_async_remove_helper_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_identifiers: set[tuple[str, str]],
    helper_has_composite_identifiers: bool,
    source_via_composite_id: bool,
) -> None:
    """Test migrating a helper off a device it co-owned before the migration split.

    The migration split the co-owned device into a source split and a helper split sharing
    the pre-migration id as their composite id. The helper's split is found via that id -
    both while it still carries the identifiers copied at the split and once the helper has
    re-registered and pruned them to its own - and whether the caller passes the composite
    id or the concrete source split. Its split is removed; its entities move onto the source
    split when a concrete device is passed, or are detached when only the composite id is.
    """
    source_config_entry = MockConfigEntry(domain=SOURCE_DOMAIN)
    source_config_entry.add_to_hass(hass)
    helper_config_entry = MockConfigEntry(domain=HELPER_DOMAIN)
    helper_config_entry.add_to_hass(hass)
    composite_id = "pre_split_composite_id"

    source_split = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={(SOURCE_DOMAIN, "1")},
    )
    helper_split = device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers=helper_identifiers,
    )
    # Both are splits of the same pre-migration device, sharing its id
    device_registry.devices[source_split.id] = attr.evolve(
        source_split,
        composite_device_id=composite_id,
    )
    device_registry.devices[helper_split.id] = attr.evolve(
        helper_split,
        composite_device_id=composite_id,
        has_composite_identifiers=helper_has_composite_identifiers,
    )
    # A helper entity on the helper's split, plus one not linked to any device
    helper_entity_entry = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        "1",
        config_entry=helper_config_entry,
        device_id=helper_split.id,
    )
    extra_helper_entity_entry = entity_registry.async_get_or_create(
        "sensor", HELPER_DOMAIN, "2", config_entry=helper_config_entry
    )

    async_remove_helper_devices(
        hass,
        helper_config_entry_id=helper_config_entry.entry_id,
        source_device_id=composite_id if source_via_composite_id else source_split.id,
    )

    # The helper's split was removed. Its entity moved onto the source split when a concrete
    # source was passed; with only the composite id there is no concrete device, so it detaches.
    expected_device_id = None if source_via_composite_id else source_split.id
    assert (
        entity_registry.async_get(helper_entity_entry.entity_id).device_id
        == expected_device_id
    )
    assert (
        entity_registry.async_get(extra_helper_entity_entry.entity_id).device_id is None
    )
    assert device_registry.async_get(helper_split.id) is None
    assert device_registry.async_get(source_split.id) is not None


async def test_async_remove_helper_devices_fork(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A helper that forked the source device via device_info is cleaned up.

    Declaring a foreign device's identifiers/connections in device_info no longer co-owns
    it; it forks a separate helper-owned device with no composite lineage. The fork is
    removed and its entities relinked to the source device, while unrelated helper-owned
    devices are left alone.
    """
    source_config_entry = MockConfigEntry(domain=SOURCE_DOMAIN)
    source_config_entry.add_to_hass(hass)
    helper_config_entry = MockConfigEntry(domain=HELPER_DOMAIN)
    helper_config_entry.add_to_hass(hass)

    source_device = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={(SOURCE_DOMAIN, "1")},
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    # The helper forked the source device by copying its identity into device_info
    fork = device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers={(SOURCE_DOMAIN, "1")},
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert fork.id != source_device.id
    assert fork.composite_device_id is None
    helper_entity_entry = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        "1",
        config_entry=helper_config_entry,
        device_id=fork.id,
    )
    # An unrelated device the helper owns, which must be left untouched
    unrelated_device = device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers={(HELPER_DOMAIN, "unrelated")},
    )
    unrelated_entity_entry = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        "2",
        config_entry=helper_config_entry,
        device_id=unrelated_device.id,
    )

    async_remove_helper_devices(
        hass,
        helper_config_entry_id=helper_config_entry.entry_id,
        source_device_id=source_device.id,
    )

    # The fork is removed and its entity relinked to the source device
    assert (
        entity_registry.async_get(helper_entity_entry.entity_id).device_id
        == source_device.id
    )
    assert device_registry.async_get(fork.id) is None
    assert device_registry.async_get(source_device.id) is not None
    # The unrelated helper-owned device and its entity are untouched
    assert device_registry.async_get(unrelated_device.id) is not None
    assert (
        entity_registry.async_get(unrelated_entity_entry.entity_id).device_id
        == unrelated_device.id
    )


async def test_async_remove_helper_devices_sweep(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Broad mode sweeps every helper device except the source and the allow-list.

    A helper that forked a device for each source it linked to, without removing the
    old forks, accumulates stale devices that don't match the current source (so the
    targeted match never sees them). sweep_helper_devices removes them and relinks the
    helper's entities - including a stranded, device-less one - to the source, while
    keep_device_ids and the source device are preserved.
    """
    source_config_entry = MockConfigEntry(domain=SOURCE_DOMAIN)
    source_config_entry.add_to_hass(hass)
    helper_config_entry = MockConfigEntry(domain=HELPER_DOMAIN)
    helper_config_entry.add_to_hass(hass)

    source_device = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={(SOURCE_DOMAIN, "current")},
    )
    # Two stale forks left behind from previously-selected source devices (their identity
    # no longer matches the current source)
    stale_fork_1 = device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers={(HELPER_DOMAIN, "stale_1")},
    )
    stale_fork_2 = device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers={(HELPER_DOMAIN, "stale_2")},
    )
    # A device the helper legitimately owns, kept via the allow-list
    kept_device = device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers={(HELPER_DOMAIN, "kept")},
    )
    entity_on_stale_1 = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        "1",
        config_entry=helper_config_entry,
        device_id=stale_fork_1.id,
    )
    entity_on_stale_2 = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        "2",
        config_entry=helper_config_entry,
        device_id=stale_fork_2.id,
    )
    # A stranded helper entity, not linked to any device
    stranded_entity = entity_registry.async_get_or_create(
        "sensor", HELPER_DOMAIN, "3", config_entry=helper_config_entry
    )
    entity_on_kept = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        "4",
        config_entry=helper_config_entry,
        device_id=kept_device.id,
    )

    async_remove_helper_devices(
        hass,
        helper_config_entry_id=helper_config_entry.entry_id,
        source_device_id=source_device.id,
        sweep_helper_devices=True,
        keep_device_ids={kept_device.id},
    )

    # Both stale forks are removed; the kept device and the source device remain
    assert device_registry.async_get(stale_fork_1.id) is None
    assert device_registry.async_get(stale_fork_2.id) is None
    assert device_registry.async_get(kept_device.id) is not None
    assert device_registry.async_get(source_device.id) is not None
    # Entities off the removed forks - and the stranded one - are relinked to the source
    for entity_entry in (entity_on_stale_1, entity_on_stale_2, stranded_entity):
        assert (
            entity_registry.async_get(entity_entry.entity_id).device_id
            == source_device.id
        )
    # The entity on the kept device is left alone
    assert (
        entity_registry.async_get(entity_on_kept.entity_id).device_id == kept_device.id
    )


@pytest.mark.parametrize(
    "source_device_id",
    [
        pytest.param("nonexistent_device_id", id="missing_device"),
        pytest.param(None, id="no_device_selected"),
    ],
)
async def test_async_remove_helper_devices_sweep_no_source(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    source_device_id: str | None,
) -> None:
    """Sweep mode removes the helper's devices when there is no source device.

    Whether the source device id points to a removed device or is None because no device is
    selected, the helper's entities are left without a device and its devices are still
    removed.
    """
    helper_config_entry = MockConfigEntry(domain=HELPER_DOMAIN)
    helper_config_entry.add_to_hass(hass)

    stale_fork = device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers={(HELPER_DOMAIN, "stale")},
    )
    entity_on_fork = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        "1",
        config_entry=helper_config_entry,
        device_id=stale_fork.id,
    )

    async_remove_helper_devices(
        hass,
        helper_config_entry_id=helper_config_entry.entry_id,
        source_device_id=source_device_id,
        sweep_helper_devices=True,
    )

    # The helper's device is removed and its entity left without a device
    assert device_registry.async_get(stale_fork.id) is None
    assert entity_registry.async_get(entity_on_fork.entity_id).device_id is None


async def test_async_remove_helper_devices_none_source_targeted_noop(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Targeted mode is a no-op when no source device is selected.

    Without sweep_helper_devices there is no duplicate to match against a missing source, so
    the helper's device and its entity's device link are left untouched.
    """
    helper_config_entry = MockConfigEntry(domain=HELPER_DOMAIN)
    helper_config_entry.add_to_hass(hass)

    helper_device = device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers={(HELPER_DOMAIN, "device")},
    )
    entity_on_device = entity_registry.async_get_or_create(
        "sensor",
        HELPER_DOMAIN,
        "1",
        config_entry=helper_config_entry,
        device_id=helper_device.id,
    )

    async_remove_helper_devices(
        hass,
        helper_config_entry_id=helper_config_entry.entry_id,
        source_device_id=None,
    )

    # Nothing is removed or relinked
    assert device_registry.async_get(helper_device.id) is not None
    assert (
        entity_registry.async_get(entity_on_device.entity_id).device_id
        == helper_device.id
    )


async def test_async_remove_helper_config_entry_from_source_device_deprecated(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The old name is a deprecated alias delegating to async_remove_helper_devices."""
    with patch(
        "homeassistant.helpers.helper_integration.async_remove_helper_devices"
    ) as mock_remove_helper_device:
        async_remove_helper_config_entry_from_source_device(
            hass,
            helper_config_entry_id="helper_config_entry_id",
            source_device_id="source_device_id",
        )

    mock_remove_helper_device.assert_called_once_with(
        hass,
        helper_config_entry_id="helper_config_entry_id",
        source_device_id="source_device_id",
    )
    assert (
        "async_remove_helper_config_entry_from_source_device was called" in caplog.text
    )
    assert "async_remove_helper_devices instead" in caplog.text


@pytest.mark.parametrize("use_entity_registry_id", [True, False])
@pytest.mark.usefixtures("source_entity_entry")
async def test_async_remove_helper_devices_helper_not_in_device(
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

    async_remove_helper_devices(
        hass,
        helper_config_entry_id=helper_config_entry.entry_id,
        source_device_id=source_device.id,
    )

    # Check we got the expected events
    assert events == []
