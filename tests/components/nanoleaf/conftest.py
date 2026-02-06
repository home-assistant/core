"""Common fixtures for Nanoleaf tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.nanoleaf import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN

from tests.common import MockConfigEntry

# Default effects for Essentials devices
ESSENTIALS_EFFECTS = ["Cozy Glow", "Neon Flex", "Party Mode"]
ESSENTIALS_CURRENT_EFFECT = "Cozy Glow"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Nanoleaf config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "10.0.0.10",
            CONF_TOKEN: "1234567890abcdef",
        },
    )


@pytest.fixture
async def mock_nanoleaf() -> AsyncGenerator[AsyncMock]:
    """Mock a Nanoleaf device."""
    with patch(
        "homeassistant.components.nanoleaf.Nanoleaf", autospec=True
    ) as mock_nanoleaf:
        client = mock_nanoleaf.return_value
        client.model = "NO_TOUCH"
        client.host = "10.0.0.10"
        client.port = 16021  # Default Nanoleaf port
        client.serial_no = "ABCDEF123456"
        client.color_temperature_max = 4500
        client.color_temperature_min = 1200
        client.is_on = False
        client.brightness = 50
        client.color_temperature = 2700
        client.hue = 120
        client.saturation = 50
        client.color_mode = "hs"
        client.effect = "Rainbow"
        client.effects_list = ["Rainbow", "Sunset", "Nemo"]
        client.firmware_version = "4.0.0"
        client.name = "Nanoleaf"
        client.manufacturer = "Nanoleaf"
        yield client


def _create_mock_response(status: int, json_data: dict | None = None, text: str = ""):
    """Create a mock aiohttp response."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data)
    response.text = AsyncMock(return_value=text)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


@pytest.fixture
def mock_essentials_aiohttp_session():
    """Mock aiohttp session for Essentials effects API."""

    def _create_session():
        session = MagicMock()

        # Mock PUT response for effects list
        effects_response = _create_mock_response(
            200,
            json_data={
                "animations": [
                    {"animName": effect, "version": "1.0"}
                    for effect in ESSENTIALS_EFFECTS
                ]
            },
        )

        # Mock GET response for current effect
        current_effect_response = _create_mock_response(
            200, text=f'"{ESSENTIALS_CURRENT_EFFECT}"'
        )

        session.put = MagicMock(return_value=effects_response)
        session.get = MagicMock(return_value=current_effect_response)
        return session

    return _create_session


@pytest.fixture
async def mock_nanoleaf_essentials(
    mock_essentials_aiohttp_session,
) -> AsyncGenerator[AsyncMock]:
    """Mock a Nanoleaf Essentials device (Rope Lights)."""
    with (
        patch(
            "homeassistant.components.nanoleaf.Nanoleaf", autospec=True
        ) as mock_nanoleaf,
        patch(
            "homeassistant.components.nanoleaf.coordinator.async_get_clientsession",
            return_value=mock_essentials_aiohttp_session(),
        ),
        patch(
            "homeassistant.components.nanoleaf.light.async_get_clientsession",
            return_value=mock_essentials_aiohttp_session(),
        ),
    ):
        client = mock_nanoleaf.return_value
        client.model = "NL72K6"  # Rope Lights
        client.host = "10.0.0.11"
        client.port = 16021  # Default Nanoleaf port
        client.serial_no = "ESSENTIALS123456"
        client.color_temperature_max = 6500
        client.color_temperature_min = 1200
        client.is_on = True
        client.brightness = 75
        client.color_temperature = 4000
        client.hue = 180
        client.saturation = 80
        client.color_mode = "hs"
        # Essentials devices don't have effects via library (fetched via HTTP)
        del client.effect
        del client.effects_list
        client.firmware_version = "4.0.0"
        client.name = "Rope Lights"
        client.manufacturer = "Nanoleaf"
        yield client


@pytest.fixture
def mock_config_entry_essentials() -> MockConfigEntry:
    """Mock a Nanoleaf Essentials config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "10.0.0.11",
            CONF_TOKEN: "essentials1234567890",
        },
        unique_id="ESSENTIALS123456",
    )
