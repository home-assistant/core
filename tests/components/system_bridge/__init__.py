"""Tests for the System Bridge integration."""

from collections.abc import Awaitable, Callable
from ipaddress import ip_address
from typing import Any

from systembridgemodels.fixtures.modules.battery import FIXTURE_BATTERY
from systembridgemodels.fixtures.modules.cpu import FIXTURE_CPU
from systembridgemodels.fixtures.modules.disks import FIXTURE_DISKS
from systembridgemodels.fixtures.modules.displays import FIXTURE_DISPLAYS
from systembridgemodels.fixtures.modules.gpus import FIXTURE_GPUS
from systembridgemodels.fixtures.modules.media import FIXTURE_MEDIA
from systembridgemodels.fixtures.modules.memory import FIXTURE_MEMORY
from systembridgemodels.fixtures.modules.processes import FIXTURE_PROCESSES
from systembridgemodels.fixtures.modules.system import FIXTURE_SYSTEM
from systembridgemodels.modules import Module, ModulesData

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

FIXTURE_TITLE = "TestSystem"

FIXTURE_REQUEST_ID = "test"

FIXTURE_MAC_ADDRESS = FIXTURE_SYSTEM.mac_address
FIXTURE_UUID = FIXTURE_SYSTEM.uuid

FIXTURE_AUTH_INPUT = {
    CONF_TOKEN: "abc-123-def-456-ghi",
}

FIXTURE_USER_INPUT = {
    CONF_TOKEN: "abc-123-def-456-ghi",
    CONF_HOST: "127.0.0.1",
    CONF_PORT: "9170",
}

FIXTURE_ZEROCONF_INPUT = {
    CONF_TOKEN: "abc-123-def-456-ghi",
    CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
    CONF_PORT: "9170",
}

FIXTURE_ZEROCONF = ZeroconfServiceInfo(
    ip_address=ip_address(FIXTURE_USER_INPUT[CONF_HOST]),
    ip_addresses=[ip_address(FIXTURE_USER_INPUT[CONF_HOST])],
    port=9170,
    hostname="test-bridge.local.",
    type="_system-bridge._tcp.local.",
    name="System Bridge - test-bridge._system-bridge._tcp.local.",
    properties={
        "address": "http://test-bridge:9170",
        "fqdn": "test-bridge",
        "host": "test-bridge",
        "ip": FIXTURE_USER_INPUT[CONF_HOST],
        "mac": FIXTURE_MAC_ADDRESS,
        "port": "9170",
        "uuid": FIXTURE_UUID,
    },
)

FIXTURE_ZEROCONF_BAD = ZeroconfServiceInfo(
    ip_address=ip_address(FIXTURE_USER_INPUT[CONF_HOST]),
    ip_addresses=[ip_address(FIXTURE_USER_INPUT[CONF_HOST])],
    port=9170,
    hostname="test-bridge.local.",
    type="_system-bridge._tcp.local.",
    name="System Bridge - test-bridge._system-bridge._tcp.local.",
    properties={
        "something": "bad",
    },
)

FIXTURE_DATA_RESPONSE = ModulesData(
    system=FIXTURE_SYSTEM,
)


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> bool:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    setup_result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return setup_result


async def mock_data_listener(
    callback: Callable[[str, Any], Awaitable[None]] | None = None,
    _: bool = False,
):
    """Mock websocket data listener."""
    if callback is not None:
        # Simulate data received from the websocket
        await callback(Module.BATTERY, FIXTURE_BATTERY)
        await callback(Module.CPU, FIXTURE_CPU)
        await callback(Module.DISKS, FIXTURE_DISKS)
        await callback(Module.DISPLAYS, FIXTURE_DISPLAYS)
        await callback(Module.GPUS, FIXTURE_GPUS)
        await callback(Module.MEDIA, FIXTURE_MEDIA)
        await callback(Module.MEMORY, FIXTURE_MEMORY)
        await callback(Module.PROCESSES, FIXTURE_PROCESSES)
        await callback(Module.SYSTEM, FIXTURE_SYSTEM)
