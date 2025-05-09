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
    with patch("os.path.isdir", return_value=True), patch("shutil.rmtree"):
        await hass.config_entries.async_setup(entry.entry_id)
        assert dict(entry.data) == legacy_config
        assert entry.version == 2
        assert entry.minor_version == 2


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
    assert entry.version == 2
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
    assert device_entries == snapshot

    device_parent = device_registry.async_get_device(identifiers={(DOMAIN, "88")})
    assert device_parent.via_device_id is None

    device = device_registry.async_get_device(identifiers={(DOMAIN, "88-9")})
    assert device.via_device_id == device_parent.id

    device_no_sub = device_registry.async_get_device(identifiers={(DOMAIN, "2")})
    assert device_no_sub.via_device_id is None
