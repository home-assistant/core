"""Snapshot benchmarks for multi-endpoint Z-Wave devices.

These tests snapshot the full device-and-entity tree produced by the zwave_js
integration for devices that expose multiple endpoints, documenting how the
integration groups endpoints into devices and entities.
"""

from unittest.mock import MagicMock

import pytest
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


@pytest.fixture
def node(request: pytest.FixtureRequest) -> Node:
    """Resolve the parametrized node fixture before integration setup."""
    return request.getfixturevalue(request.param)


@pytest.mark.parametrize(
    "node",
    [
        # Vision ZL7432 In Wall Dual Relay Switch: two independently controllable
        # relay outputs on one in-wall module. Endpoints 1 and 2 each expose
        # SWITCH_BINARY currentValue, one per relay output; the manual does not
        # state which endpoint maps to which physical load.
        pytest.param("vision_security_zl7432", id="vision_zl7432"),
        # Fibaro FGR-223 Roller Shutter 3: single motor output controlling a roller
        # or venetian shutter. Endpoint 1 is the primary shutter control
        # (SWITCH_MULTILEVEL for position). Endpoint 2 exposes slat/tilt control for
        # venetian mode; it produces a secondary cover entity disabled by the
        # integration by default (disabled_by: integration), so a registry entry
        # exists but the entity is off unless the user enables it.
        pytest.param("fibaro_fgr223_shutter", id="fibaro_fgr223"),
        # Shelly/Qubino QNSH-001P10 Wave Shutter: one bi-directional motor (O1 up,
        # O2 down), same topology as the FGR-223. Endpoint 1 is shutter position;
        # endpoint 2 is the venetian slat tilt, present only when operating mode
        # (param 71) is Venetian. The endpoint-2 cover is disabled by the
        # integration, but unlike the FGR-223 this endpoint also mirrors the Meter
        # and Notification CCs, yielding a duplicate set of enabled sensor, binary
        # sensor and button entities.
        pytest.param("shelly_qnsh_001P10_shutter", id="shelly_qnsh_001p10"),
        # Merten 507801 Connect Roller Shutter: a 1-gang receiver with a single
        # motor output (two interlocked make contacts for up/down). Endpoints 1
        # and 2 have identical capabilities (SWITCH_MULTILEVEL + PROTECTION); the
        # manufacturer documents no endpoint semantics at all, and the integration
        # discovers endpoint 2 disabled.
        pytest.param("merten_507801", id="merten_507801"),
        # Inovelli LZW36 Light/Fan Combo: an in-wall switch paired with a canopy
        # module in the fan; only the switch is the Z-Wave node, driving the module
        # over proprietary RF. Endpoint 1 is the light (SWITCH_MULTILEVEL dimming),
        # endpoint 2 the fan motor (SWITCH_MULTILEVEL speed). The two loads are
        # physically separate and independently controllable.
        pytest.param("inovelli_lzw36", id="inovelli_lzw36"),
        # Heatit Z-TRM6 floor thermostat: thermostat input on endpoint 0/1. Three
        # separate temperature sensor probes report via SENSOR_MULTILEVEL Air
        # temperature: endpoint 2 is the internal (room) air sensor, endpoint 3 is
        # an external air sensor, and endpoint 4 is the floor sensor. Each probe is
        # a physically distinct input.
        pytest.param("climate_heatit_z_trm6", id="heatit_z_trm6"),
        # Heatit Z-TRM3 floor thermostat: same multi-sensor topology as the Z-TRM6:
        # thermostat input on endpoint 0/1, three separate temperature sensor probes
        # reporting Air temperature on endpoints 2 (internal), 3 (external), and 4
        # (floor).
        pytest.param("climate_heatit_z_trm3", id="heatit_z_trm3"),
        # Heatit Z-TRM2fx floor thermostat: thermostat on endpoint 1. Unlike the
        # Z-TRM3 and Z-TRM6, the endpoint order differs and there is no internal
        # room sensor: endpoint 2 is the external room sensor and endpoint 3 is the
        # floor sensor (it still reports sensor type "Air temperature"). Endpoint 4
        # is the internal relay (Binary Switch + Meter), not a sensor. The BASIC
        # currentValue/targetValue on endpoints 2 and 3 are undocumented.
        pytest.param("climate_heatit_z_trm2fx", id="heatit_z_trm2fx"),
    ],
    indirect=True,
)
async def test_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    node: Node,
    integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device tree for a multi-endpoint Z-Wave device."""
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    assert (
        _snapshot_device_tree(hass, device_registry, entity_registry, node_device)
        == snapshot
    )
