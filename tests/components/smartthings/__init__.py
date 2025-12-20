"""Tests for the SmartThings integration."""

import sys
import types
from typing import Any
from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, DeviceEvent, DeviceHealthEvent
from pysmartthings.models import HealthStatus
from syrupy.assertion import SnapshotAssertion

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
    component: str = MAIN,
) -> None:
    """Trigger an update."""
    event = DeviceEvent(
        "abc",
        "abc",
        "abc",
        device_id,
        component,
        capability,
        attribute,
        value,
        data,
    )
    for call in mock.add_unspecified_device_event_listener.call_args_list:
        call[0][0](event)
    for call in mock.add_device_event_listener.call_args_list:
        if call[0][0] == device_id:
            call[0][3](event)
    for call in mock.add_device_capability_event_listener.call_args_list:
        if call[0][0] == device_id and call[0][2] == capability:
            call[0][3](event)
    await hass.async_block_till_done()


async def trigger_health_update(
    hass: HomeAssistant, mock: AsyncMock, device_id: str, status: HealthStatus
) -> None:
    """Trigger a health update."""
    event = DeviceHealthEvent("abc", "abc", status)
    for call in mock.add_device_availability_event_listener.call_args_list:
        if call[0][0] == device_id:
            call[0][1](event)
    await hass.async_block_till_done()


def ensure_haffmpeg_stubs() -> None:
    """Ensure haffmpeg stubs are available for SmartThings tests."""
    if "haffmpeg" in sys.modules:
        return

    haffmpeg_module = types.ModuleType("haffmpeg")
    haffmpeg_core_module = types.ModuleType("haffmpeg.core")
    haffmpeg_tools_module = types.ModuleType("haffmpeg.tools")

    class _StubHAFFmpeg: ...

    class _StubFFVersion:
        def __init__(self, bin_path: str | None = None) -> None:
            self.bin_path = bin_path

        async def get_version(self) -> str:
            return "4.0.0"

    class _StubImageFrame: ...

    haffmpeg_core_module.HAFFmpeg = _StubHAFFmpeg
    haffmpeg_tools_module.IMAGE_JPEG = b""
    haffmpeg_tools_module.FFVersion = _StubFFVersion
    haffmpeg_tools_module.ImageFrame = _StubImageFrame
    haffmpeg_module.core = haffmpeg_core_module
    haffmpeg_module.tools = haffmpeg_tools_module

    sys.modules["haffmpeg"] = haffmpeg_module
    sys.modules["haffmpeg.core"] = haffmpeg_core_module
    sys.modules["haffmpeg.tools"] = haffmpeg_tools_module


ensure_haffmpeg_stubs()
