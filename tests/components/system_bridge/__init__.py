"""Tests for the System Bridge integration."""

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from ipaddress import ip_address
from typing import Any

from systembridgeconnector.const import TYPE_DATA_UPDATE
from systembridgemodels.const import MODEL_SYSTEM
from systembridgemodels.modules import System
from systembridgemodels.response import Response

from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN

FIXTURE_MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
FIXTURE_UUID = "e91bf575-56f3-4c83-8f42-70ac17adcd33"

FIXTURE_AUTH_INPUT = {CONF_TOKEN: "abc-123-def-456-ghi"}

FIXTURE_USER_INPUT = {
    CONF_TOKEN: "abc-123-def-456-ghi",
    CONF_HOST: "test-bridge",
    CONF_PORT: "9170",
}

FIXTURE_ZEROCONF_INPUT = {
    CONF_TOKEN: "abc-123-def-456-ghi",
    CONF_HOST: "1.1.1.1",
    CONF_PORT: "9170",
}

FIXTURE_ZEROCONF = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    port=9170,
    hostname="test-bridge.local.",
    type="_system-bridge._tcp.local.",
    name="System Bridge - test-bridge._system-bridge._tcp.local.",
    properties={
        "address": "http://test-bridge:9170",
        "fqdn": "test-bridge",
        "host": "test-bridge",
        "ip": "1.1.1.1",
        "mac": FIXTURE_MAC_ADDRESS,
        "port": "9170",
        "uuid": FIXTURE_UUID,
    },
)

FIXTURE_ZEROCONF_BAD = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    port=9170,
    hostname="test-bridge.local.",
    type="_system-bridge._tcp.local.",
    name="System Bridge - test-bridge._system-bridge._tcp.local.",
    properties={
        "something": "bad",
    },
)


FIXTURE_SYSTEM = System(
    boot_time=1,
    fqdn="",
    hostname="1.1.1.1",
    ip_address_4="1.1.1.1",
    mac_address=FIXTURE_MAC_ADDRESS,
    platform="",
    platform_version="",
    uptime=1,
    uuid=FIXTURE_UUID,
    version="",
    version_latest="",
    version_newer_available=False,
    users=[],
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


async def mock_data_listener(
    self,
    callback: Callable[[str, Any], Awaitable[None]] | None = None,
    _: bool = False,
):
    """Mock websocket data listener."""
    if callback is not None:
        # Simulate data received from the websocket
        await callback(MODEL_SYSTEM, FIXTURE_SYSTEM)
