"""Test fixtures for rainbird."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from typing import Any
from unittest.mock import patch

from pyrainbird import encryption
import pytest

from homeassistant.components.rainbird import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

ComponentSetup = Callable[[], Awaitable[bool]]

HOST = "example.com"
URL = "http://example.com/stick"
PASSWORD = "password"

#
# Response payloads below come from pyrainbird test cases.
#

# Get serial number Command 0x85. Serial is 0x12635436566
SERIAL_RESPONSE = "850000012635436566"
# Get available stations command 0x83
AVAILABLE_STATIONS_RESPONSE = "83017F000000"  # Mask for 7 zones
EMPTY_STATIONS_RESPONSE = "830000000000"
# Get zone state command 0xBF.
ZONE_3_ON_RESPONSE = "BF0004000000"  # Zone 3 is on
ZONE_5_ON_RESPONSE = "BF0010000000"  # Zone 5 is on
ZONE_OFF_RESPONSE = "BF0000000000"  # All zones off
ZONE_STATE_OFF_RESPONSE = "BF0000000000"
# Get rain sensor state command 0XBE
RAIN_SENSOR_OFF = "BE00"
RAIN_SENSOR_ON = "BE01"
# Get rain delay command 0xB6
RAIN_DELAY = "B60010"  # 0x10 is 16
RAIN_DELAY_OFF = "B60000"
# ACK command 0x10, Echo 0x06
ACK_ECHO = "0106"

CONFIG = {
    DOMAIN: {
        "host": HOST,
        "password": PASSWORD,
        "trigger_time": 360,
    }
}


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture
def yaml_config() -> dict[str, Any]:
    """Fixture for configuration.yaml."""
    return CONFIG


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    platforms: list[str],
    yaml_config: dict[str, Any],
) -> Generator[ComponentSetup, None, None]:
    """Fixture for setting up the component."""

    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):

        async def func() -> bool:
            result = await async_setup_component(hass, DOMAIN, yaml_config)
            await hass.async_block_till_done()
            return result

        yield func


def rainbird_response(data: str) -> bytes:
    """Create a fake API response."""
    return encryption.encrypt(
        '{"jsonrpc": "2.0", "result": {"data":"%s"}, "id": 1} ' % data,
        PASSWORD,
    )


def mock_response(data: str) -> AiohttpClientMockResponse:
    """Create a fake AiohttpClientMockResponse."""
    return AiohttpClientMockResponse("POST", URL, response=rainbird_response(data))


@pytest.fixture(name="responses")
def mock_responses() -> list[AiohttpClientMockResponse]:
    """Fixture to set up a list of fake API responsees for tests to extend."""
    return [mock_response(SERIAL_RESPONSE)]


@pytest.fixture(autouse=True)
def handle_responses(
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Fixture for command mocking for fake responses to the API url."""

    async def handle(method, url, data) -> AiohttpClientMockResponse:
        return responses.pop(0)

    aioclient_mock.post(URL, side_effect=handle)
