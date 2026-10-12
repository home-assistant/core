"""Snapshot benchmarks for multi-endpoint Z-Wave devices.

These tests snapshot the full device-and-entity tree produced by the zwave_js
integration for devices that expose multiple endpoints, documenting how the
integration groups endpoints into devices and entities.
"""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


def _snapshot_device_tree(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    node_device: dr.DeviceEntry,
) -> dict:
    """Build a stable, snapshot-friendly representation of a node's device tree.

    Returns a nested dict keyed by the stable Z-Wave device id, where the node
    device maps to its name, its entities (an ``entity_id -> original_name``
    mapping) and its child devices (a dict keyed by child device id, each with
    the same name and entities).  The snapshot is stable across runs because raw
    device UUIDs are not included.
    """

    def _zwave_device_id(device: dr.AnyDeviceEntry) -> str:
        """Return the stable Z-Wave base device id from a device's identifiers.

        A node device can carry both the base ``{home_id}-{node_id}`` identifier
        and a longer extended ``{home_id}-{node_id}-{mfr}:{type}:{id}`` one; the
        base is always the shortest, so pick the shortest by length.
        """
        return min(
            (
                identifier
                for domain, identifier in device.identifiers
                if domain == DOMAIN
            ),
            key=len,
        )

    def _device_entity_names(device_id: str) -> dict[str, str | None]:
        # Syrupy sorts mapping keys on output, so the entity_id keys end up
        # ordered in the snapshot regardless of insertion order here.
        return {
            entry.entity_id: entry.original_name
            for entry in er.async_entries_for_device(
                entity_registry, device_id, include_disabled_entities=True
            )
        }

    return {
        _zwave_device_id(node_device): {
            "name": node_device.name,
            "entities": _device_entity_names(node_device.id),
            "children": {
                _zwave_device_id(child): {
                    "name": child.name,
                    "entities": _device_entity_names(child.id),
                }
                for child in dr.async_entries_for_parent_device(
                    device_registry, node_device.id
                )
            },
        }
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
        # venetian mode; it produces a secondary cover entity that the integration
        # disables by default, so a registry entry exists (and is included in the
        # snapshot) but the entity is off unless the user enables it.
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
        _snapshot_device_tree(device_registry, entity_registry, node_device) == snapshot
    )
