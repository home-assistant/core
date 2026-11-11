"""Test migration and rediscovery of legacy Gree config entries."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gree.const import DOMAIN
from homeassistant.components.gree.discovery import (
    device_info_to_data,
    normalize_identifier,
)
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component


def _add_legacy_entry(
    hass: HomeAssistant,
    disabled_by: ConfigEntryDisabler | None = None,
) -> MockConfigEntry:
    """Add a shared v1 entry as if restored from storage."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="gree",
        data={},
        disabled_by=disabled_by,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    "identifiers", [(), ("legacy-device",)], ids=["empty", "populated"]
)
async def test_legacy_entry_becomes_persistent_discovery_owner(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    identifiers: tuple[str, ...],
) -> None:
    """Migration retains the owner, clears legacy records, and never enrolls devices."""
    discovery.mock_devices.clear()
    source = _add_legacy_entry(hass)
    other = MockConfigEntry(domain="example", version=2, unique_id="other", data={})
    other.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("example", "other")},
    )
    other_entity = entity_registry.async_get_or_create(
        "sensor",
        "example",
        "other",
        config_entry=other,
        device_id=other_device.id,
    )
    for identifier in identifiers:
        old_device = device_registry.async_get_or_create(
            config_entry_id=source.entry_id,
            identifiers={(DOMAIN, identifier)},
        )
        entity_registry.async_get_or_create(
            "climate",
            DOMAIN,
            identifier,
            config_entry=source,
            device_id=old_device.id,
        )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.config_entries.async_get_entry(source.entry_id) is source
    assert source.version == 2
    assert source.minor_version == 1
    assert source.unique_id == DOMAIN
    assert source.data == {}
    assert hass.config_entries.async_entries(DOMAIN) == [source]
    assert not dr.async_entries_for_config_entry(device_registry, source.entry_id)
    assert not er.async_entries_for_config_entry(entity_registry, source.entry_id)
    assert dr.async_entries_for_config_entry(device_registry, other.entry_id) == [
        other_device
    ]
    assert er.async_entries_for_config_entry(entity_registry, other.entry_id) == [
        other_entity
    ]
    assert not hass.states.async_all("climate")
    assert not hass.config_entries.flow.async_progress()
    device().bind.assert_not_awaited()
    device().update_state.assert_not_awaited()


async def test_disabled_legacy_entry_converts_when_enabled(
    hass: HomeAssistant,
    discovery: MagicMock,
) -> None:
    """A disabled source converts only when enabled and can stop discovery again."""
    discovery.mock_devices.clear()
    source = _add_legacy_entry(hass, ConfigEntryDisabler.USER)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert source.state is ConfigEntryState.NOT_LOADED
    assert source.version == 1
    assert source.disabled_by is ConfigEntryDisabler.USER
    assert not discovery.instances

    await hass.config_entries.async_set_disabled_by(source.entry_id, None)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert source.state is ConfigEntryState.LOADED
    assert source.version == 2
    assert source.minor_version == 1
    assert source.unique_id == DOMAIN
    assert source.data == {}
    assert hass.config_entries.async_get_entry(source.entry_id) is source

    await hass.config_entries.async_set_disabled_by(
        source.entry_id, ConfigEntryDisabler.USER
    )
    assert source.state is ConfigEntryState.NOT_LOADED
    assert source.disabled_by is ConfigEntryDisabler.USER
    assert hass.config_entries.async_entries(DOMAIN) == [source]


async def test_migrated_legacy_device_can_be_enrolled_after_discovery_confirmation(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Rediscovery offers enrollment but creates a per-device entry only on consent."""
    candidate = device()
    discovery.mock_devices = [candidate]
    source = _add_legacy_entry(hass)
    old_device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={(DOMAIN, candidate.device_info.mac)},
    )
    entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        candidate.device_info.mac,
        config_entry=source,
        device_id=old_device.id,
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.config_entries.async_get_entry(source.entry_id) is source
    assert source.version == 2
    assert source.minor_version == 1
    assert source.unique_id == DOMAIN
    assert source.data == {}
    assert hass.config_entries.async_entries(DOMAIN) == [source]
    assert not device_registry.devices
    assert not entity_registry.entities
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "discovery_confirm"
    assert flows[0]["context"]["unique_id"] == normalize_identifier(
        candidate.device_info.mac
    )
    candidate.bind.assert_not_awaited()
    assert not hass.states.async_all("climate")

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.version == 2
    assert entry.unique_id == normalize_identifier(candidate.device_info.mac)
    assert entry.data == device_info_to_data(candidate.device_info)
    assert hass.config_entries.async_entries(DOMAIN) == [source, entry]
    candidate.bind.assert_awaited()
    candidate.close.assert_called()
