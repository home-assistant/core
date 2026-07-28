"""Tests for iAquaLink diagnostics."""

from unittest.mock import AsyncMock, patch

from iaqualink.client import AqualinkClient
from iaqualink.systems.iaqua.device import IaquaLightSwitch, IaquaSensor
from iaqualink.systems.iaqua.system import IaquaSystem
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import get_aqualink_device, get_aqualink_system

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.data["serial_number"] = "SN00001"
    system.online = True
    system.update = AsyncMock()
    systems = {system.serial: system}
    light = get_aqualink_device(
        system, name="aux_1", cls=IaquaLightSwitch, data={"state": "1"}
    )
    sensor = get_aqualink_device(
        system, name="pool_temp", cls=IaquaSensor, data={"value": "82"}
    )
    devices = {light.name: light, sensor.name: sensor}
    system.devices = devices
    system.get_devices = AsyncMock(return_value=devices)

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value=systems,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
