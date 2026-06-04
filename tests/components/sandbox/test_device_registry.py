"""Tests — device_info bridging from the sandbox to main's registries."""

from typing import Any

import pytest

from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.bridge import (
    SandboxBridge,
    SandboxEntityDescription,
)
from homeassistant.components.sandbox.channel import Channel, ChannelRemoteError
from homeassistant.components.sandbox.messages import make_entity_description
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from ._helpers import make_channel_pair

from tests.common import MockConfigEntry


async def _wire(
    hass: HomeAssistant,
) -> tuple[SandboxBridge, Channel, Channel]:
    """Build a bridge connected to an in-memory channel-pair sandbox stub."""
    main_channel, sandbox_channel = make_channel_pair(name_a="main", name_b="sandbox")
    bridge = SandboxBridge(hass, group="built-in", channel=main_channel)
    main_channel.start()
    sandbox_channel.start()
    return bridge, main_channel, sandbox_channel


@pytest.fixture(name="entry")
def _entry_fixture(hass: HomeAssistant) -> ConfigEntry:
    entry = MockConfigEntry(
        domain="light",
        title="Sandboxed Hue Hub",
        data={"host": "1.2.3.4"},
        sandbox="built-in",
    )
    entry.add_to_hass(hass)
    return entry


def _register_payload(
    entry: ConfigEntry,
    *,
    sandbox_entity_id: str = "light.kitchen",
    unique_id: str = "sandbox-kitchen",
    device_info: dict[str, Any] | None = None,
) -> pb.EntityDescription:
    return make_entity_description(
        entry_id=entry.entry_id,
        domain="light",
        sandbox_entity_id=sandbox_entity_id,
        unique_id=unique_id,
        supported_features=0,
        capabilities={"supported_color_modes": ["onoff"]},
        initial_state="on",
        initial_attributes={"color_mode": "onoff"},
        device_info=device_info,
    )


async def test_register_entity_creates_device_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A sandboxed register_entity with device_info lands in main's device_registry."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    payload = _register_payload(
        entry,
        device_info={
            "identifiers": [["sandboxed_hue", "bulb-001"]],
            "name": "Kitchen Bulb",
            "manufacturer": "Acme",
            "model": "GlowMax",
        },
    )

    try:
        result = await sandbox_channel.call("sandbox/register_entity", payload)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    device = dr.async_get(hass).async_get_device(
        identifiers={("sandboxed_hue", "bulb-001")}
    )
    assert device is not None
    assert device.name == "Kitchen Bulb"
    assert device.manufacturer == "Acme"
    assert device.model == "GlowMax"
    # The DeviceEntry must be linked to the sandboxed config entry.
    assert entry.entry_id in device.config_entries
    # The main-side entity_registry entry has device_id set to that DeviceEntry.
    er_entry = er.async_get(hass).async_get(result.entity_id)
    assert er_entry is not None
    assert er_entry.device_id == device.id


async def test_register_entity_propagates_device_id_to_proxy(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """The proxy entity reports the freshly-created device_id."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    payload = _register_payload(
        entry,
        device_info={
            "identifiers": [["sandboxed_hue", "bulb-002"]],
            "name": "Lounge Bulb",
        },
    )

    try:
        await sandbox_channel.call("sandbox/register_entity", payload)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    proxy = bridge._entities["light.kitchen"]
    assert proxy.description.device_id is not None
    device = dr.async_get(hass).async_get(proxy.description.device_id)
    assert device is not None
    assert ("sandboxed_hue", "bulb-002") in device.identifiers
    # The framework also wired entity.device_entry through async_add_entities.
    assert proxy.device_entry is not None
    assert proxy.device_entry.id == proxy.description.device_id


async def test_register_entity_without_device_info_leaves_device_id_unset(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Backwards compatibility: no device_info in payload → no device registered."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    payload = _register_payload(entry)  # no device_info

    try:
        await sandbox_channel.call("sandbox/register_entity", payload)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    proxy = bridge._entities["light.kitchen"]
    assert proxy.description.device_info is None
    assert proxy.description.device_id is None
    # No device created against this entry.
    assert not any(
        entry.entry_id in d.config_entries for d in dr.async_get(hass).devices.values()
    )


async def test_area_assignment_propagates_to_proxy(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Assigning the DeviceEntry to an area surfaces on the proxy via HA's normal path."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    payload = _register_payload(
        entry,
        device_info={
            "identifiers": [["sandboxed_hue", "bulb-003"]],
            "name": "Hallway",
        },
    )

    try:
        result = await sandbox_channel.call("sandbox/register_entity", payload)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    area = ar.async_get(hass).async_get_or_create("Hallway")
    device = dr.async_get(hass).async_get_device(
        identifiers={("sandboxed_hue", "bulb-003")}
    )
    assert device is not None
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    # The proxy's entity_registry entry inherits area through HA's standard
    # device → entity area-resolution path (no sandbox code involvement).
    refreshed_device = dr.async_get(hass).async_get(device.id)
    assert refreshed_device is not None
    assert refreshed_device.area_id == area.id
    er_entry = er.async_get(hass).async_get(result.entity_id)
    assert er_entry is not None
    assert er_entry.device_id == device.id


async def test_invalid_device_info_surfaces_remote_error(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Bad device_info (e.g. empty identifiers + connections) is rejected with HomeAssistantError."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    payload = _register_payload(
        entry,
        device_info={"identifiers": [], "connections": [], "name": "Nameless"},
    )

    try:
        with pytest.raises(ChannelRemoteError):
            await sandbox_channel.call("sandbox/register_entity", payload)
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_description_from_proto_reconstructs_typed_device_info() -> None:
    """``SandboxEntityDescription.from_proto`` rebuilds set/tuple shapes."""
    description = SandboxEntityDescription.from_proto(
        make_entity_description(
            entry_id="abc",
            domain="sensor",
            sandbox_entity_id="sensor.temp",
            device_info={
                "identifiers": [["foo", "1"], ["foo", "2"]],
                "connections": [["mac", "00:11:22"]],
                "via_device": ["parent_domain", "parent-1"],
                "entry_type": "service",
                "name": "Thermo",
            },
        )
    )
    assert description.device_info is not None
    info = description.device_info
    assert info["identifiers"] == {("foo", "1"), ("foo", "2")}
    assert info["connections"] == {("mac", "00:11:22")}
    assert info["via_device"] == ("parent_domain", "parent-1")
    assert info["entry_type"] is dr.DeviceEntryType.SERVICE
    assert info["name"] == "Thermo"
