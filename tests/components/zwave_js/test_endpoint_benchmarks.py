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
        # Vision ZL7432 In Wall Dual Relay Switch: two independent relay outputs:
        # endpoint 1 controls load 1 and endpoint 2 controls load 2. Both expose
        # SWITCH_BINARY currentValue, so they are two separate physical switch
        # outputs on the same in-wall module.
        pytest.param("vision_security_zl7432", id="vision_zl7432"),
        # Fibaro FGR-223 Roller Shutter 3: single motor output controlling a roller
        # or venetian shutter. Endpoint 1 is the primary shutter control
        # (SWITCH_MULTILEVEL for position). Endpoint 2 exposes slat/tilt control for
        # venetian mode; it produces a secondary cover entity disabled by the
        # integration by default (disabled_by: integration), so a registry entry
        # exists but the entity is off unless the user enables it.
        pytest.param("fibaro_fgr223_shutter", id="fibaro_fgr223"),
        # Shelly/Qubino QNSH-001P10 Wave Shutter: two genuine motor outputs sharing
        # one device. Endpoint 1 is the primary shutter (SWITCH_MULTILEVEL for
        # position). Endpoint 2 is a second independent output and produces its own
        # full set of entities: cover, binary sensors, power sensors, and buttons,
        # most of which are enabled by default. The secondary cover entity itself is
        # disabled by the integration, but the endpoint-2 monitoring entities are not.
        pytest.param("shelly_qnsh_001P10_shutter", id="shelly_qnsh_001p10"),
        # Merten 507801 Connect Roller Shutter: single motor output controlling a
        # roller shutter. Endpoint 1 is the primary shutter control
        # (SWITCH_MULTILEVEL). Endpoint 2 exposes an additional control mode (e.g.
        # slat/scene control) and is created as a disabled-by-integration entity by
        # default; it is not suppressed, so it still produces a registry entry.
        pytest.param("merten_507801", id="merten_507801"),
        # Inovelli LZW36 Light/Fan Combo: two independent outputs on a single
        # ceiling-fan canopy module: endpoint 1 controls the light kit
        # (SWITCH_MULTILEVEL for dimming) and endpoint 2 controls the fan motor
        # (SWITCH_MULTILEVEL for speed). The two outputs are physically separate
        # and are meant to be controlled independently.
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
        # Heatit Z-TRM2fx floor thermostat: thermostat control on endpoint 0/1.
        # Endpoints 2 and 3 each expose an Air temperature sensor and a BASIC class
        # entity. Unlike the Z-TRM3 and Z-TRM6, this device has only two temperature
        # probes (endpoints 2 and 3) and no endpoint-4 floor sensor.
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
