"""Benchmark the Matter device topology for multi-endpoint devices.

This captures, per fixture, the node device, any child devices, bridge
(``via_device``) links and the entity names on each device. It is a benchmark:
changes to how multi-endpoint devices are represented (e.g. splitting endpoints
into child devices) show up directly as a diff of the snapshot.
"""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import snapshot_matter_devices


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize(
    "node_fixture",
    [
        # A dual-socket plug: two On/Off Plug-in Unit endpoints of the same type.
        "eve_energy_20ecn4101",
        # Multiple endpoints sharing a primary attribute but of different device
        # types (a dimmer with an extra color endpoint).
        "inovelli_vtm31",
        # Many Generic Switch (button) endpoints.
        "haojai_switch",
        # A window covering plus two Generic Switch endpoints, carrying semantic
        # tags.
        "aqara_shutter_switch_h2",
        # Bridges: bridged devices are separate HA devices linked via via_device.
        "mock_composed_bridge",
        "fritz_bridge",
        # Nested composed devices (appliances): part endpoints collapse onto their
        # compose parent's device.
        "silabs_refrigerator",
        "mock_air_purifier",
    ],
)
async def test_multi_endpoint_device_topology(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Benchmark devices, child devices and entity names for multi-endpoint devices."""
    snapshot_matter_devices(hass, device_registry, entity_registry, snapshot)
