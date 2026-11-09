"""Tests for the Velbus component initialisation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion
from velbusaio.exceptions import VelbusConnectionFailed

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.velbus import (
    VelbusConfigEntry,
    _child_name_from_registry,
    _is_channel_subdevice_identifier,
    _migrate_via_devices_to_children,
    async_remove_config_entry_device,
)
from homeassistant.components.velbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, CONF_PORT, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_entity_id, init_integration
from .const import PORT_TCP


async def test_setup_connection_failed(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
    controller: MagicMock,
) -> None:
    """Test the setup that fails during velbus connect."""
    controller.return_value.connect.side_effect = VelbusConnectionFailed()
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_start_failed(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
    controller: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup fails during velbus start task, should result in no entries."""
    controller.return_value.start.side_effect = ConnectionError()
    await init_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert (
        er.async_entries_for_config_entry(entity_registry, config_entry.entry_id) == []
    )


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Test being able to unload an entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_device_identifier_migration(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test being able to unload an entry."""
    original_identifier = (DOMAIN, "module_address", "module_serial")
    target_identifier = (DOMAIN, "module_address")

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={original_identifier},  # type: ignore[arg-type]
        name="channel_name",
        manufacturer="Velleman",
        model="module_type_name",
        sw_version="module_sw_version",
    )
    assert device_registry.async_get_device_by_identifier(
        original_identifier,  # type: ignore[arg-type]
        config_entry.entry_id,
    )
    assert (
        device_registry.async_get_device_by_identifier(
            target_identifier, config_entry.entry_id
        )
        is None
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device_by_identifier(
        original_identifier,  # type: ignore[arg-type]
        config_entry.entry_id,
    )
    device_entry = device_registry.async_get_device_by_identifier(
        target_identifier, config_entry.entry_id
    )
    assert device_entry
    assert device_entry.name == "channel_name"
    assert device_entry.manufacturer == "Velleman"
    assert device_entry.model == "module_type_name"
    assert device_entry.sw_version == "module_sw_version"


async def test_migrate_config_entry(
    hass: HomeAssistant,
    controller: MagicMock,
) -> None:
    """Test successful migration of entry data."""
    legacy_config = {CONF_NAME: "fake_name", CONF_PORT: "1.2.3.4:5678"}
    entry = MockConfigEntry(domain=DOMAIN, unique_id="my own id", data=legacy_config)
    assert entry.version == 1
    assert entry.minor_version == 1

    entry.add_to_hass(hass)

    # test in case we do not have a cache
    with (
        patch("os.path.isdir", return_value=True),
        patch("shutil.rmtree") as mock_rmtree,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert dict(entry.data) == legacy_config
        assert entry.version == 3
        assert entry.minor_version == 2
        mock_rmtree.assert_called_once()


async def test_migrate_config_entry_32(
    hass: HomeAssistant,
    controller: MagicMock,
) -> None:
    """Test successful migration of entry data."""
    legacy_config = {CONF_NAME: "fake_name", CONF_PORT: "1.2.3.4:5678"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="my own id",
        data=legacy_config,
        version=2,
        minor_version=2,
    )
    assert entry.version == 2
    assert entry.minor_version == 2

    entry.add_to_hass(hass)

    # test in case we do not have a cache
    with (
        patch("os.path.isdir", return_value=True),
        patch("shutil.rmtree") as mock_rmtree,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert dict(entry.data) == legacy_config
        assert entry.version == 3
        assert entry.minor_version == 2
        mock_rmtree.assert_called_once()


@pytest.mark.parametrize(
    ("unique_id", "expected"),
    [("vid:pid_serial_manufacturer_decription", "serial"), (None, None)],
)
async def test_migrate_config_entry_unique_id(
    hass: HomeAssistant,
    controller: AsyncMock,
    unique_id: str,
    expected: str,
) -> None:
    """Test the migration of unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: PORT_TCP, CONF_NAME: "velbus home"},
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.unique_id == expected
    assert entry.version == 3
    assert entry.minor_version == 2


async def test_api_call(
    hass: HomeAssistant,
    mock_relay: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the api call decorator action."""
    await init_integration(hass, config_entry)
    entity_id = get_entity_id(entity_registry, SWITCH_DOMAIN, "qwerty123-55")

    mock_relay.turn_on.side_effect = OSError()
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert exc_info.value.translation_placeholders == {"entity": entity_id}


def register_legacy_channel_sub_device(
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    parent_address: str,
    channel: str,
    *,
    name: str,
) -> dr.DeviceEntry:
    """Register a Velbus channel device created before child devices."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, parent_address)},
        name=f"Kitchen ({parent_address})",
        manufacturer="Velleman",
        model="VMB2BLE",
    )
    return device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"{parent_address}-{channel}")},
        name=name,
        manufacturer="Velleman",
        model="VMB2BLE",
        via_device_id=parent.id,
    )


async def test_device_registry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the velbus device registry."""
    await init_integration(hass, config_entry)

    device_entries = sorted(
        dr.async_entries_for_config_entry(device_registry, config_entry.entry_id),
        key=lambda entry: list(entry.identifiers)[0][1],
    )
    for device_entry in device_entries:
        assert device_entry == snapshot(name=list(device_entry.identifiers)[0][1])

    child_entries = sorted(
        dr.async_child_entries_for_config_entry(device_registry, config_entry.entry_id),
        key=lambda entry: list(entry.identifiers)[0][1],
    )
    for child_entry in child_entries:
        assert child_entry == snapshot(name=list(child_entry.identifiers)[0][1])

    device_parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, "88"), config_entry.entry_id
    )
    assert device_parent is not None
    assert device_parent.via_device_id is None

    device = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, "88-9"), config_entry.entry_id
    )
    assert device is not None
    assert device.parent_device_id == device_parent.id

    device_no_sub = device_registry.async_get_device_by_identifier(
        (DOMAIN, "2"), config_entry.entry_id
    )
    assert device_no_sub is not None
    assert device_no_sub.via_device_id is None


async def test_legacy_sub_device_converted_to_child_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a legacy via_device channel is converted to a child device."""
    legacy_device = register_legacy_channel_sub_device(
        device_registry,
        config_entry,
        "88",
        "9",
        name="Kitchen (VMB2BLE) - CoverName",
    )
    device_registry.async_config_entry_unloaded(config_entry.entry_id)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get(legacy_device.id)
    assert isinstance(device_entry, dr.ChildDeviceEntry)
    device_parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, "88"), config_entry.entry_id
    )
    assert device_parent is not None
    assert device_entry.parent_device_id == device_parent.id

    cover_entity_id = get_entity_id(entity_registry, "cover", "1234-9")
    cover_entry = entity_registry.async_get(cover_entity_id)
    assert cover_entry is not None
    assert cover_entry.device_id == legacy_device.id


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that any Velbus device can be removed."""
    await init_integration(hass, config_entry)

    # Active device (found on bus) can be removed; scan will recreate it
    active_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1"), config_entry.entry_id
    )
    assert active_device is not None
    result = await async_remove_config_entry_device(hass, config_entry, active_device)
    assert result is True

    # Stale device (not on bus) can also be removed
    stale_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "999")},
        name="Missing Module",
        manufacturer="Velleman",
        model="VMBX",
    )
    result = await async_remove_config_entry_device(hass, config_entry, stale_device)
    assert result is True
    device_registry.async_remove_device(stale_device.id)

    stale_device_after = device_registry.async_get(stale_device.id)
    assert (
        stale_device_after is None
        or stale_device_after.config_entry_id != config_entry.entry_id
    )


async def test_remove_config_entry_device_detaches_subdevices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that removing a device also removes its child devices."""
    await init_integration(hass, config_entry)

    stale_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "999")},
        name="Missing Module",
        manufacturer="Velleman",
        model="VMBX",
    )
    sub_device = device_registry.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "999-1")},
        name="Channel 1",
        parent_device_id=stale_device.id,
    )

    result = await async_remove_config_entry_device(hass, config_entry, stale_device)
    assert result is True

    assert device_registry.async_get(sub_device.id) is None


@pytest.mark.parametrize(
    ("child_name", "parent_name", "expected"),
    [
        ("Kitchen (VMB2BLE) - CoverName", "Kitchen (VMB2BLE)", "CoverName"),
        ("Custom channel name", "Kitchen (VMB2BLE)", "Custom channel name"),
        (None, "Kitchen (VMB2BLE)", None),
        ("Relay", None, "Relay"),
    ],
)
def test_child_name_from_registry(
    child_name: str | None, parent_name: str | None, expected: str | None
) -> None:
    """Test stripping a legacy parent prefix from channel device names."""
    assert _child_name_from_registry(child_name, parent_name) == expected


@pytest.mark.parametrize(
    ("child_identifiers", "parent_identifiers", "expected"),
    [
        ({(DOMAIN, "88-9")}, {(DOMAIN, "88")}, True),
        ({(DOMAIN, "88-")}, {(DOMAIN, "88")}, False),
        ({(DOMAIN, "99")}, {(DOMAIN, "88")}, False),
        ({(DOMAIN, "88-9"), (DOMAIN, "extra")}, {(DOMAIN, "88")}, False),
        ({(DOMAIN, "88-9")}, {(DOMAIN, "88"), (DOMAIN, "other")}, False),
    ],
)
def test_is_channel_subdevice_identifier(
    child_identifiers: set[tuple[str, str]],
    parent_identifiers: set[tuple[str, str]],
    expected: bool,
) -> None:
    """Test channel sub-device identifier validation."""
    assert (
        _is_channel_subdevice_identifier(child_identifiers, parent_identifiers)
        is expected
    )


async def test_migrate_via_devices_to_children(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test legacy via_device channel devices are converted by the migration helper."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "88")},
        name="Kitchen (VMB2BLE)",
        manufacturer="Velleman",
        model="VMB2BLE",
    )
    legacy = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "88-1")},
        name="Kitchen (VMB2BLE) - Relay",
        manufacturer="Velleman",
        model="VMB4RYNO",
        via_device_id=parent.id,
    )
    device_registry.async_config_entry_unloaded(config_entry.entry_id)

    _migrate_via_devices_to_children(hass, config_entry.entry_id)

    device_entry = device_registry.async_get(legacy.id)
    assert isinstance(device_entry, dr.ChildDeviceEntry)
    assert device_entry.parent_device_id == parent.id
    assert device_entry.name == "Relay"
    assert device_entry.identifiers == {(DOMAIN, "88-1")}


async def test_migrate_via_devices_to_children_skips_non_channel(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the migration helper ignores via links that are not module channels."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "88")},
        name="Kitchen (VMB2BLE)",
        manufacturer="Velleman",
        model="VMB2BLE",
    )
    other = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "99")},
        name="Other product",
        manufacturer="Velleman",
        model="VMBX",
        via_device_id=parent.id,
    )

    _migrate_via_devices_to_children(hass, config_entry.entry_id)

    device_entry = device_registry.async_get(other.id)
    assert device_entry is not None
    assert not isinstance(device_entry, dr.ChildDeviceEntry)
    assert device_entry.via_device_id == parent.id


# velbus-aio maps both the spec key and the display name to the class name, because
# Property.get_name() returned the spec key before velbus-aio 2026.4.1 and the display
# name from that release onwards; both forms exist as original_name in the wild.
_PROPERTY_KEY_MAP = {
    "selected_program": "SelectedProgram",
    "Selected program": "SelectedProgram",
    "light_value": "LightValue",
    "Light value": "LightValue",
}


@pytest.mark.parametrize(
    ("domain", "device_serial", "old_unique_id", "original_name", "expected_unique_id"),
    [
        pytest.param(
            "select",
            "test_serial",
            "test_serial-0-program_select",
            "selected_program",
            "test_serial-SelectedProgram",
            id="rename_select_spec_key",
        ),
        pytest.param(
            "select",
            "test_serial",
            "test_serial-0-program_select",
            "Selected program",
            "test_serial-SelectedProgram",
            id="rename_select_display_name",
        ),
        pytest.param(
            "select",
            "test_serial",
            "test_serial-5-program_select",
            "selected_program",
            "test_serial-SelectedProgram",
            id="rename_select_legacy_channel",
        ),
        pytest.param(
            "sensor",
            "test_serial",
            "test_serial-0",
            "light_value",
            "test_serial-LightValue",
            id="rename_sensor",
        ),
        pytest.param(
            "sensor",
            "overwritten_serial",
            "test_serial-0",
            "light_value",
            "test_serial-LightValue",
            id="serial_taken_from_unique_id_not_device",
        ),
        pytest.param(
            "select",
            "test_serial",
            "test_serial-SelectedProgram",
            "selected_program",
            "test_serial-SelectedProgram",
            id="already_correct",
        ),
        pytest.param(
            "select",
            "test_serial",
            "test_serial-old_format",
            None,
            "test_serial-old_format",
            id="skipped_without_name",
        ),
        pytest.param(
            "select",
            "test_serial",
            "test_serial-old_format",
            "not_a_property",
            "test_serial-old_format",
            id="skipped_unknown_name",
        ),
        pytest.param(
            "sensor",
            "test_serial",
            "test_serial-3",
            "light_value",
            "test_serial-3",
            id="skipped_colliding_channel",
        ),
    ],
)
async def test_migrate_property_unique_ids(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    controller: MagicMock,
    domain: str,
    device_serial: str,
    old_unique_id: str,
    original_name: str | None,
    expected_unique_id: str,
) -> None:
    """Test the property unique_id migration for every legacy and skip case."""
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "1")},
        serial_number=device_serial,
    )
    entity = entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        old_unique_id,
        config_entry=config_entry,
        device_id=device.id,
        original_name=original_name,
    )

    with patch(
        "homeassistant.components.velbus.get_property_key_map",
        return_value=_PROPERTY_KEY_MAP,
    ):
        await init_integration(hass, config_entry)

    migrated = entity_registry.async_get(entity.entity_id)
    assert migrated
    assert migrated.unique_id == expected_unique_id


async def test_migrate_property_unique_ids_remove_stale(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    controller: MagicMock,
) -> None:
    """Test that a stale property entity is removed when the correct one already exists."""
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "1")},
        serial_number="test_serial",
    )
    entity_registry.async_get_or_create(
        "select",
        DOMAIN,
        "test_serial-SelectedProgram",
        config_entry=config_entry,
        device_id=device.id,
        original_name="selected_program",
    )
    entity_registry.async_get_or_create(
        "select",
        DOMAIN,
        "test_serial-0-program_select",
        config_entry=config_entry,
        device_id=device.id,
        original_name="selected_program",
    )

    with patch(
        "homeassistant.components.velbus.get_property_key_map",
        return_value=_PROPERTY_KEY_MAP,
    ):
        await init_integration(hass, config_entry)

    assert not entity_registry.async_get_entity_id(
        "select", DOMAIN, "test_serial-0-program_select"
    )
    assert entity_registry.async_get_entity_id(
        "select", DOMAIN, "test_serial-SelectedProgram"
    )


async def test_migrate_property_unique_ids_preserves_entity_id(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    controller: MagicMock,
) -> None:
    """Test that a migrated property keeps its entity_id once the bus scan registers it."""
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "2")},
        serial_number="a1b2c3d4e5f6",
    )
    # Same serial as the scanned LightValue property, so migrating before the scan makes
    # the scan reuse this entry instead of registering a second one.
    legacy_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "a1b2c3d4e5f6-0",
        config_entry=config_entry,
        device_id=device.id,
        original_name="light_value",
        suggested_object_id="legacy_light_value",
    )
    assert legacy_entity.entity_id == "sensor.legacy_light_value"

    with patch(
        "homeassistant.components.velbus.get_property_key_map",
        return_value=_PROPERTY_KEY_MAP,
    ):
        await init_integration(hass, config_entry)

    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, "a1b2c3d4e5f6-LightValue")
        == "sensor.legacy_light_value"
    )
