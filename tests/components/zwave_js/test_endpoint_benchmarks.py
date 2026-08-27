"""Snapshot benchmarks for multi-endpoint Z-Wave devices.

These tests snapshot the full device-and-entity tree produced by the zwave_js
integration for devices that expose multiple endpoints, documenting how the
integration groups endpoints into devices and entities.
"""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


def _snapshot_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    node_device: dr.DeviceEntry,
) -> dict:
    """Build a stable, snapshot-friendly representation of a node's device tree.

    Returns a dict with the node device name, its identifier suffixes, all
    entities on the node device, and a list of child devices (if any), each
    with their name, identifiers, and entities.  The snapshot is stable across
    runs because raw device UUIDs are not included.
    """

    def _stable_identifiers(device: dr.DeviceEntry) -> list[str]:
        return sorted(
            f"{domain}:{identifier}" for domain, identifier in device.identifiers
        )

    def _entities_for_device(device_id: str) -> list[dict]:
        entries = er.async_entries_for_device(
            entity_registry, device_id, include_disabled_entities=True
        )
        return sorted(
            [
                {
                    "entity_id": entry.entity_id,
                    "original_name": entry.original_name,
                    "disabled_by": str(entry.disabled_by),
                }
                for entry in entries
            ],
            key=lambda e: e["entity_id"],
        )

    child_devices = sorted(
        dr.async_entries_for_parent_device(device_registry, node_device.id),
        key=_stable_identifiers,
    )

    return {
        "node_device": {
            "name": node_device.name,
            "identifiers": _stable_identifiers(node_device),
            "entities": _entities_for_device(node_device.id),
        },
        "child_devices": [
            {
                "name": child.name,
                "identifiers": _stable_identifiers(child),
                "entities": _entities_for_device(child.id),
            }
            for child in child_devices
        ],
    }


async def test_vision_zl7432_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    vision_security_zl7432: Node,
    integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device tree for Vision ZL7432 In Wall Dual Relay Switch.

    Two independent relay outputs: endpoint 1 controls load 1 and endpoint 2
    controls load 2.  Both expose SWITCH_BINARY currentValue, so they are two
    separate physical switch outputs on the same in-wall module.
    """
    node = vision_security_zl7432
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    assert (
        _snapshot_device_tree(hass, device_registry, entity_registry, node_device)
        == snapshot
    )


async def test_fibaro_fgr223_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    fibaro_fgr223_shutter: Node,
    integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device tree for Fibaro FGR-223 Roller Shutter 3.

    Single motor output controlling a roller or venetian shutter.  Endpoint 1
    is the primary shutter control (SWITCH_MULTILEVEL for position).  Endpoint 2
    exposes slat/tilt control for venetian mode but duplicates endpoint 1's motor
    in roller-shutter mode; its discovery schema suppresses it so no redundant
    entity is created.
    """
    node = fibaro_fgr223_shutter
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    assert (
        _snapshot_device_tree(hass, device_registry, entity_registry, node_device)
        == snapshot
    )


async def test_shelly_qnsh_001p10_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    shelly_qnsh_001P10_shutter: Node,
    integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device tree for Shelly/Qubino QNSH-001P10 Wave Shutter.

    Single motor output controlling a roller or venetian shutter.  Endpoint 1
    is the primary shutter control (SWITCH_MULTILEVEL for position).  Endpoint 2
    exposes slat/tilt control for venetian mode but duplicates endpoint 1's motor
    in roller-shutter mode; its discovery schema suppresses it so no redundant
    entity is created.
    """
    node = shelly_qnsh_001P10_shutter
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    assert (
        _snapshot_device_tree(hass, device_registry, entity_registry, node_device)
        == snapshot
    )


async def test_merten_507801_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    merten_507801: Node,
    integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device tree for Merten 507801 Connect Roller Shutter.

    Single motor output controlling a roller shutter.  Endpoint 1 is the primary
    shutter control (SWITCH_MULTILEVEL).  Endpoint 2 exposes an additional
    control mode (e.g. slat/scene control) and is created as a disabled entity
    by default; it is not suppressed, so it still produces a registry entry.
    """
    node = merten_507801
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    assert (
        _snapshot_device_tree(hass, device_registry, entity_registry, node_device)
        == snapshot
    )


async def test_inovelli_lzw36_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    inovelli_lzw36: Node,
    integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device tree for Inovelli LZW36 Light/Fan Combo.

    Two independent outputs on a single ceiling-fan canopy module: endpoint 1
    controls the light kit (SWITCH_MULTILEVEL for dimming) and endpoint 2
    controls the fan motor (SWITCH_MULTILEVEL for speed).  The two outputs are
    physically separate and are meant to be controlled independently.
    """
    node = inovelli_lzw36
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    assert (
        _snapshot_device_tree(hass, device_registry, entity_registry, node_device)
        == snapshot
    )


async def test_heatit_z_trm6_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_heatit_z_trm6: Node,
    integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device tree for Heatit Z-TRM6 floor thermostat.

    The thermostat input is on endpoint 0/1.  Three separate temperature sensor
    probes report via SENSOR_MULTILEVEL Air temperature: endpoint 2 is the
    internal (room) air sensor, endpoint 3 is an external air sensor, and
    endpoint 4 is the floor sensor.  Each probe is a physically distinct input.
    """
    node = climate_heatit_z_trm6
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    assert (
        _snapshot_device_tree(hass, device_registry, entity_registry, node_device)
        == snapshot
    )


async def test_heatit_z_trm3_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device tree for Heatit Z-TRM3 floor thermostat.

    Same multi-sensor topology as the Z-TRM6: the thermostat input is on
    endpoint 0/1, and three separate temperature sensor probes report via
    SENSOR_MULTILEVEL Air temperature on endpoints 2 (internal), 3 (external),
    and 4 (floor).
    """
    node = climate_heatit_z_trm3
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    assert (
        _snapshot_device_tree(hass, device_registry, entity_registry, node_device)
        == snapshot
    )


async def test_heatit_z_trm2fx_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_heatit_z_trm2fx: Node,
    integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device tree for Heatit Z-TRM2fx floor thermostat.

    Similar multi-sensor topology to the Z-TRM3: thermostat input on endpoint
    0/1, with multiple temperature sensor probes reporting SENSOR_MULTILEVEL
    Air temperature on separate endpoints.
    """
    node = climate_heatit_z_trm2fx
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    assert (
        _snapshot_device_tree(hass, device_registry, entity_registry, node_device)
        == snapshot
    )
