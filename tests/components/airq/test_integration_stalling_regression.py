"""Test that the coordinator does not hang with unresponding server.

Users reported that the integration was stalling silently at random intervals.
This was identified to be due to an incorrect timeout in aioairq and was fixed
in aioairq==0.4.7 and homeassistant==2025.10.3.
This is the regression test.
"""

import asyncio
import time

import pytest
import pytest_asyncio

from homeassistant.components.airq import AirQCoordinator
from homeassistant.components.airq.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TIMEOUT_DEFAULT = 15
TIMEOUT_HANGING = TIMEOUT_DEFAULT * 3
TIMEOUT_SAFETY = TIMEOUT_DEFAULT * 2
IP = "127.0.0.1"


@pytest_asyncio.fixture
async def hanging_server():
    """TCP server that accepts connections but never sends data.

    This makes HTTP clients wait forever for the status line / headers.
    """

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            # Keep the connection open; don't read or write HTTP data.
            await asyncio.sleep(TIMEOUT_HANGING)
        finally:
            writer.close()

    # pick any free ephemeral port on localhost and bind the server to it
    server = await asyncio.start_server(handler, host=IP, port=0)
    # get the actual selected port
    port = server.sockets[0].getsockname()[1]
    try:
        yield (IP, port)
    finally:
        server.close()


@pytest.mark.usefixtures("socket_enabled")
async def test_coordinator_timeout_with_hanging_device(
    hass: HomeAssistant,
    hanging_server,
) -> None:
    """Test that AirQCoordinator times out by itself instead of getting stuck."""
    host, port = hanging_server

    # Create config entry with the actual hanging server address
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: f"{host}:{port}",  # Use actual port!
            CONF_PASSWORD: "test_password",
        },
        unique_id="test_hanging_device",
    )

    # Create coordinator
    coordinator = AirQCoordinator(hass, config_entry)

    started = time.perf_counter()

    with pytest.raises(asyncio.TimeoutError):
        async with asyncio.timeout(TIMEOUT_SAFETY):
            await coordinator._async_update_data()

    elapsed = time.perf_counter() - started

    assert elapsed < TIMEOUT_DEFAULT + 1, (
        f"Expected ~{TIMEOUT_DEFAULT}s, got {elapsed:.1f}s (aioairq==0.4.6 behavior)"
    )
