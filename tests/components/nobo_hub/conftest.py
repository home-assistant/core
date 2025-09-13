"""Fixtures for the Nobo Hub component tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.nobo_hub import CONF_AUTO_DISCOVERED, CONF_SERIAL, DOMAIN
from homeassistant.components.nobo_hub.const import (
    ATTR_SERIAL,
    ATTR_TEMP_COMFORT_C,
    ATTR_TEMP_ECO_C,
)
from homeassistant.const import CONF_IP_ADDRESS

from tests.common import MockConfigEntry


@pytest.fixture
async def mock_nobo_hub() -> AsyncGenerator[AsyncMock]:
    """Fixture to mock the nobo hub."""
    with patch("homeassistant.components.nobo_hub.nobo", autospec=True) as mock_nobo:
        nobo = mock_nobo.return_value
        nobo.zones = {
            "device_1": {
                "name": "Device 1",
                "zone_id": "zone_1",
                "model": nobo.MODELS["168"],
                ATTR_TEMP_COMFORT_C: 22.0,
                ATTR_TEMP_ECO_C: 18.0,
            },
            "device_2": {
                "name": "Device 2",
                "zone_id": "zone_1",
                "model": nobo.MODELS["180"],
                ATTR_TEMP_COMFORT_C: 22.0,
                ATTR_TEMP_ECO_C: 18.0,
            },
        }
        nobo.hub_serial = "218886794"
        nobo.hub_info = {
            ATTR_SERIAL: "218886794",
        }
        nobo.components = {
            "component_1": {
                "serial": "abc",
                "status": "online",
                "zone_id": "zone_1",
            },
        }
        yield nobo


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={
            CONF_SERIAL: "218886794",
            CONF_IP_ADDRESS: "10.0.0.1",
            CONF_AUTO_DISCOVERED: True,
        },
        unique_id="218886794",
    )
