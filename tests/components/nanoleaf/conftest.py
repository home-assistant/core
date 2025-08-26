"""Common fixtures for Nanoleaf tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.nanoleaf import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN

from tests.common import MockConfigEntry


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
