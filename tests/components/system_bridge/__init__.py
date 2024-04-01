"""Tests for the System Bridge integration."""

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from ipaddress import ip_address
from typing import Any

from systembridgeconnector.const import TYPE_DATA_UPDATE
from systembridgemodels.const import (
    MODEL_BATTERY,
    MODEL_CPU,
    MODEL_DISKS,
    MODEL_DISPLAYS,
    MODEL_GPUS,
    MODEL_MEDIA,
    MODEL_MEMORY,
    MODEL_PROCESSES,
    MODEL_SYSTEM,
)
from systembridgemodels.fixtures.modules.battery import FIXTURE_BATTERY
from systembridgemodels.fixtures.modules.cpu import FIXTURE_CPU
from systembridgemodels.fixtures.modules.disks import FIXTURE_DISKS
from systembridgemodels.fixtures.modules.displays import FIXTURE_DISPLAYS
from systembridgemodels.fixtures.modules.gpus import FIXTURE_GPUS
from systembridgemodels.fixtures.modules.media import FIXTURE_MEDIA
from systembridgemodels.fixtures.modules.memory import FIXTURE_MEMORY
from systembridgemodels.fixtures.modules.processes import FIXTURE_PROCESSES
from systembridgemodels.fixtures.modules.system import FIXTURE_SYSTEM
from systembridgemodels.response import Response

from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FIXTURE_TITLE = "TestSystem"

FIXTURE_REQUEST_ID = "test"

FIXTURE_MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
FIXTURE_UUID = "uuid"

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

FIXTURE_ZEROCONF = zeroconf.ZeroconfServiceInfo(
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

FIXTURE_ZEROCONF_BAD = zeroconf.ZeroconfServiceInfo(
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

FIXTURE_DATA_RESPONSE = Response(
    id="1234",
    type=TYPE_DATA_UPDATE,
    subtype=None,
    message="Data received",
    module=MODEL_SYSTEM,
    data=asdict(FIXTURE_SYSTEM),
)

FIXTURE_DATA_RESPONSE_BAD = Response(
    id="1234",
    type=TYPE_DATA_UPDATE,
    subtype=None,
    message="Data received",
    module=MODEL_SYSTEM,
    data={},
)

FIXTURE_DATA_RESPONSE_BAD = Response(
    id="1234",
    type=TYPE_DATA_UPDATE,
    subtype=None,
    message="Data received",
    module=MODEL_SYSTEM,
    data={},
)


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)


async def mock_data_listener(
    callback: Callable[[str, Any], Awaitable[None]] | None = None,
    _: bool = False,
):
    """Mock websocket data listener."""
    if callback is not None:
        # Simulate data received from the websocket
        await callback(MODEL_BATTERY, FIXTURE_BATTERY)
        await callback(MODEL_CPU, FIXTURE_CPU)
        await callback(MODEL_DISKS, FIXTURE_DISKS)
        await callback(MODEL_DISPLAYS, FIXTURE_DISPLAYS)
        await callback(MODEL_GPUS, FIXTURE_GPUS)
        await callback(MODEL_MEDIA, FIXTURE_MEDIA)
        await callback(MODEL_MEMORY, FIXTURE_MEMORY)
        await callback(MODEL_PROCESSES, FIXTURE_PROCESSES)
        await callback(MODEL_SYSTEM, FIXTURE_SYSTEM)
