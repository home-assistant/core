"""Tests for the Velbus component initialisation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from velbusaio.exceptions import VelbusConnectionFailed

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.velbus import VelbusConfigEntry
from homeassistant.components.velbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, CONF_PORT, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .const import PORT_TCP

from tests.common import MockConfigEntry


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
    """Test the setup that fails during velbus start task, should result in no entries."""
    controller.return_value.start.side_effect = ConnectionError()
    await init_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert (
        er.async_entries_for_config_entry(entity_registry, config_entry.entry_id) == []
    )


async def test_setup_start_failed_clears_cache(
    hass: HomeAssistant,
    controller: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a corrupt cache is cleared when the start task fails with an unexpected error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: PORT_TCP, CONF_NAME: "velbus home"},
        version=3,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    controller.return_value.start.side_effect = Exception("corrupt cache")
    with (
        patch("homeassistant.components.velbus.os.path.isdir", return_value=True),
        patch("homeassistant.components.velbus.shutil.rmtree") as mock_rmtree,
    ):
        await init_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    mock_rmtree.assert_called_once()
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
    original_identifiers = {(DOMAIN, "module_address", "module_serial")}
    target_identifiers = {(DOMAIN, "module_address")}

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=original_identifiers,  # type: ignore[arg-type]
        name="channel_name",
        manufacturer="Velleman",
        model="module_type_name",
        sw_version="module_sw_version",
    )
    assert device_registry.async_get_device(
        identifiers=original_identifiers  # type: ignore[arg-type]
    )
    assert not device_registry.async_get_device(identifiers=target_identifiers)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device(
        identifiers=original_identifiers  # type: ignore[arg-type]
    )
    device_entry = device_registry.async_get_device(identifiers=target_identifiers)
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
) -> None:
    """Test the api call decorator action."""
    await init_integration(hass, config_entry)

    mock_relay.turn_on.side_effect = OSError()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.living_room_relayname"},
            blocking=True,
        )


_PROPERTY_KEY_MAP = {"selected_program": "SelectedProgram"}


async def test_migrate_property_unique_ids_rename(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    controller: MagicMock,
) -> None:
    """Test that a property entity with an outdated unique_id gets renamed."""
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "1")},
        serial_number="test_serial",
    )
    entity_registry.async_get_or_create(
        "select",
        DOMAIN,
        "test_serial-old_format",
        config_entry=config_entry,
        device_id=device.id,
        original_name="selected_program",
    )

    with patch(
        "homeassistant.components.velbus._build_property_key_map",
        return_value=_PROPERTY_KEY_MAP,
    ):
        await init_integration(hass, config_entry)

    assert not entity_registry.async_get_entity_id(
        "select", DOMAIN, "test_serial-old_format"
    )
    assert entity_registry.async_get_entity_id(
        "select", DOMAIN, "test_serial-SelectedProgram"
    )


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
    # The correct entity already exists
    entity_registry.async_get_or_create(
        "select",
        DOMAIN,
        "test_serial-SelectedProgram",
        config_entry=config_entry,
        device_id=device.id,
        original_name="selected_program",
    )
    # The stale entity with an old unique_id also exists
    entity_registry.async_get_or_create(
        "select",
        DOMAIN,
        "test_serial-old_format",
        config_entry=config_entry,
        device_id=device.id,
        original_name="selected_program",
    )

    with patch(
        "homeassistant.components.velbus._build_property_key_map",
        return_value=_PROPERTY_KEY_MAP,
    ):
        await init_integration(hass, config_entry)

    assert not entity_registry.async_get_entity_id(
        "select", DOMAIN, "test_serial-old_format"
    )
    assert entity_registry.async_get_entity_id(
        "select", DOMAIN, "test_serial-SelectedProgram"
    )


async def test_migrate_property_unique_ids_already_correct(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    controller: MagicMock,
) -> None:
    """Test that a property entity with a correct unique_id is left unchanged."""
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

    with patch(
        "homeassistant.components.velbus._build_property_key_map",
        return_value=_PROPERTY_KEY_MAP,
    ):
        await init_integration(hass, config_entry)

    assert entity_registry.async_get_entity_id(
        "select", DOMAIN, "test_serial-SelectedProgram"
    )


async def test_device_registry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the velbus device registry."""
    await init_integration(hass, config_entry)

    # Ensure devices are correctly registered
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    # Sort by identifier to ensure consistent order in snapshot
    assert sorted(device_entries, key=lambda x: list(x.identifiers)[0][1]) == snapshot

    device_parent = device_registry.async_get_device(identifiers={(DOMAIN, "88")})
    assert device_parent.via_device_id is None

    device = device_registry.async_get_device(identifiers={(DOMAIN, "88-9")})
    assert device.via_device_id == device_parent.id

    device_no_sub = device_registry.async_get_device(identifiers={(DOMAIN, "2")})
    assert device_no_sub.via_device_id is None


async def test_stale_device_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that a repair issue is created for devices not found during scan."""
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "999")},
        name="Missing Module (VMBX)",
        manufacturer="Velleman",
        model="VMBX",
    )

    await init_integration(hass, config_entry)

    issue = issue_registry.async_get_issue(
        DOMAIN, f"stale_device_{config_entry.entry_id}_999"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders["address"] == "999"


async def test_stale_device_issue_cleared_when_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that the stale device repair issue is cleared when module is found again."""
    issue_id = f"stale_device_{config_entry.entry_id}_1"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="stale_device",
        translation_placeholders={"name": "Some Module", "address": "1"},
    )
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await init_integration(hass, config_entry)

    # Address "1" is found by the mock — issue must be cleared
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_stale_subdevice_no_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that sub-devices (via_device_id set) do not trigger a stale device issue."""
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "999")},
        name="Missing Module",
        manufacturer="Velleman",
        model="VMB2BLE",
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "999-1")},
        name="Missing Module Channel 1",
        manufacturer="Velleman",
        model="VMB2BLE",
        via_device=(DOMAIN, "999"),
    )

    await init_integration(hass, config_entry)

    # Parent raises an issue, sub-device must not
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"stale_device_{config_entry.entry_id}_999"
        )
        is not None
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"stale_device_{config_entry.entry_id}_999-1"
        )
        is None
    )
