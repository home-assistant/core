"""Tests for the SmartThings integration."""

from typing import Any
from unittest.mock import AsyncMock

from pysmartthings.models import Attribute, Capability, DeviceEvent
from syrupy import SnapshotAssertion

from homeassistant.components.smartthings.const import MAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def snapshot_smartthings_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Snapshot SmartThings entities."""
    entities = hass.states.async_all(platform)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")


def set_attribute_value(
    mock: AsyncMock,
    capability: Capability,
    attribute: Attribute,
    value: Any,
    component: str = MAIN,
) -> None:
    """Set the value of an attribute."""
    mock.get_device_status.return_value[component][capability][attribute].value = value


async def trigger_update(
    hass: HomeAssistant,
    mock: AsyncMock,
    device_id: str,
    capability: Capability,
    attribute: Attribute,
    value: str | float | dict[str, Any] | list[Any] | None,
    data: dict[str, Any] | None = None,
) -> None:
    """Trigger an update."""
    for call in mock.add_device_event_listener.call_args_list:
        if call[0][0] == device_id and call[0][2] == capability:
            call[0][3](
                DeviceEvent(
                    "abc",
                    "abc",
                    "abc",
                    device_id,
                    MAIN,
                    capability,
                    attribute,
                    value,
                    data,
                )
            )
    await hass.async_block_till_done()
