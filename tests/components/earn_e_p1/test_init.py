"""Tests for the EARN-E P1 Meter integration setup."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    CONF_SERIAL,
    DOMAIN,
    MOCK_DEVICE_DATA,
    MOCK_EQUIPMENT_ID,
    MOCK_EQUIPMENT_ID_2,
    MOCK_HOST,
    MOCK_HOST_2,
    MOCK_NEW_SERIAL,
    MOCK_SERIAL,
    MOCK_SERIAL_2,
    trigger_callback,
)


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test successful setup of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_listener.start.assert_awaited_once()
    mock_listener.register.assert_called_once()


async def test_setup_entry_oserror_raises_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test that OSError during setup raises ConfigEntryNotReady."""
    mock_listener.start = AsyncMock(side_effect=OSError("Address in use"))

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test unloading a config entry stops the shared listener."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_listener.unregister.assert_called()
    mock_listener.stop.assert_awaited()


async def test_unload_entry_keeps_listener_for_remaining_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_2: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test the shared listener survives until the last entry is unloaded."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry_2.state is ConfigEntryState.LOADED
    mock_listener.start.assert_awaited_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_listener.stop.assert_not_awaited()

    await hass.config_entries.async_unload(mock_config_entry_2.entry_id)
    await hass.async_block_till_done()

    mock_listener.stop.assert_awaited_once()


async def test_unload_entry_keeps_listener_while_other_entry_sets_up(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test unloading an entry leaves a listener another setup already claimed."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST_2, CONF_SERIAL: MOCK_SERIAL_2},
        unique_id=MOCK_EQUIPMENT_ID_2,
        minor_version=2,
    )
    second_entry.add_to_hass(hass)

    def unload_first_entry(*_: object) -> None:
        """Unload the first entry while the second one is still setting up."""
        hass.async_create_task(
            hass.config_entries.async_unload(mock_config_entry.entry_id)
        )

    # The coordinator registers with the listener right after claiming it.
    mock_listener.register.side_effect = unload_first_entry

    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert second_entry.state is ConfigEntryState.LOADED
    mock_listener.stop.assert_not_awaited()


async def test_concurrent_setup_starts_listener_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_2: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test entries setting up at the same time share a single listener."""
    starting = asyncio.Event()
    resume = asyncio.Event()

    async def blocked_start() -> None:
        starting.set()
        await resume.wait()

    mock_listener.start.side_effect = blocked_start

    setup = hass.async_create_task(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    await starting.wait()
    resume.set()
    await setup
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry_2.state is ConfigEntryState.LOADED
    mock_listener.start.assert_awaited_once()


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device info is correctly populated."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_EQUIPMENT_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot


async def test_device_registry_not_updated_on_identical_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry is not updated when model/sw_version are unchanged."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_EQUIPMENT_ID), mock_config_entry.entry_id
    )
    assert device is not None
    first_modified = device.modified_at

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_EQUIPMENT_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.modified_at == first_modified


async def test_device_registry_updated_on_sw_version_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry is updated when sw_version changes."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_EQUIPMENT_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "1.0.0"

    trigger_callback(mock_listener, sw_version="2.0.0")
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_EQUIPMENT_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "2.0.0"


async def test_migrate_entry_drops_mac(
    hass: HomeAssistant, mock_legacy_config_entry: MockConfigEntry
) -> None:
    """Test migrating to 1.2 drops the MAC, which now comes from the serial."""
    await hass.config_entries.async_setup(mock_legacy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_legacy_config_entry.state is ConfigEntryState.LOADED
    assert mock_legacy_config_entry.minor_version == 2
    assert mock_legacy_config_entry.data == {
        CONF_HOST: MOCK_HOST,
        CONF_SERIAL: MOCK_SERIAL,
    }
    assert CONF_MAC not in mock_legacy_config_entry.data


async def test_legacy_entry_moves_to_meter(
    hass: HomeAssistant,
    mock_legacy_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an entry keyed on the dongle moves to the meter, keeping entity IDs."""
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{MOCK_SERIAL}_power_delivered",
        config_entry=mock_legacy_config_entry,
        suggested_object_id="renamed_power",
    )
    await hass.config_entries.async_setup(mock_legacy_config_entry.entry_id)
    await hass.async_block_till_done()

    # The first packet adds the remaining entities and re-keys the entry.
    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    assert mock_legacy_config_entry.unique_id == MOCK_EQUIPMENT_ID
    assert mock_legacy_config_entry.state is ConfigEntryState.LOADED

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_legacy_config_entry.entry_id
    )
    assert {entry.unique_id for entry in entries} == {
        f"{MOCK_EQUIPMENT_ID}_{key}" for key in MOCK_DEVICE_DATA
    }
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{MOCK_EQUIPMENT_ID}_power_delivered"
        )
        == "sensor.renamed_power"
    )
    assert hass.states.get("sensor.renamed_power") is not None
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_EQUIPMENT_ID), mock_legacy_config_entry.entry_id
    )
    assert device is not None
    assert device.identifiers == {(DOMAIN, MOCK_EQUIPMENT_ID)}


@pytest.mark.parametrize(
    "equipment_id",
    [pytest.param(None, id="missing"), pytest.param("", id="empty")],
)
async def test_legacy_entry_without_equipment_id_stays(
    hass: HomeAssistant,
    mock_legacy_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    equipment_id: str | None,
) -> None:
    """Test an entry stays keyed on the dongle when the meter sends no ID."""
    await hass.config_entries.async_setup(mock_legacy_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener, equipment_id=equipment_id)
    await hass.async_block_till_done()

    assert mock_legacy_config_entry.unique_id == MOCK_SERIAL


async def test_legacy_entry_meter_already_configured(
    hass: HomeAssistant,
    mock_legacy_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an entry is not moved onto a meter another entry already uses."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST_2, CONF_SERIAL: MOCK_SERIAL_2},
        unique_id=MOCK_EQUIPMENT_ID,
        minor_version=2,
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)
    await hass.config_entries.async_setup(mock_legacy_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    assert mock_legacy_config_entry.unique_id == MOCK_SERIAL
    assert caplog.text.count("already uses that meter") == 1


async def test_swapped_dongle_replaces_mac(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device drops the MAC of a swapped-out dongle."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_NEW_SERIAL},
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_EQUIPMENT_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.connections == {
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(MOCK_NEW_SERIAL))
    }


async def test_registries_move_when_serial_changed_before_setup(
    hass: HomeAssistant,
    mock_listener: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the registries move to the meter even if the serial changed first."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"EARN-E P1 ({MOCK_HOST})",
        data={CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_NEW_SERIAL},
        unique_id=MOCK_EQUIPMENT_ID,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(MOCK_SERIAL))},
    )
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{MOCK_SERIAL}_power_delivered",
        config_entry=entry,
        suggested_object_id="renamed_power",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(devices) == 1
    assert devices[0].identifiers == {(DOMAIN, MOCK_EQUIPMENT_ID)}
    assert devices[0].connections == {
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(MOCK_NEW_SERIAL))
    }
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{MOCK_EQUIPMENT_ID}_power_delivered"
        )
        == "sensor.renamed_power"
    )
