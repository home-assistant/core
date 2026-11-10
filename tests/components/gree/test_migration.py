"""Test removal and rediscovery of legacy Gree config entries."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gree.const import DOMAIN
from homeassistant.components.gree.discovery import (
    device_info_to_data,
    normalize_identifier,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component


def _add_legacy_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a shared v1 entry as if restored from storage."""
    entry = MockConfigEntry(domain=DOMAIN, version=1, unique_id="gree", data={})
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    "identifiers", [(), ("legacy-device",)], ids=["empty", "populated"]
)
async def test_legacy_entry_is_removed_without_replacement(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    identifiers: tuple[str, ...],
) -> None:
    """Removing a v1 entry cleans its registry records without binding a device."""
    discovery.mock_devices.clear()
    source = _add_legacy_entry(hass)
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

    assert hass.config_entries.async_get_entry(source.entry_id) is None
    assert not hass.config_entries.async_entries(DOMAIN)
    assert not device_registry.devices
    assert not entity_registry.entities
    assert not hass.states.async_all("climate")
    device().bind.assert_not_awaited()
    device().update_state.assert_not_awaited()


async def test_removed_legacy_device_can_be_enrolled_after_discovery_confirmation(
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

    assert hass.config_entries.async_get_entry(source.entry_id) is None
    assert not hass.config_entries.async_entries(DOMAIN)
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
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    candidate.bind.assert_awaited()
    candidate.close.assert_called()
