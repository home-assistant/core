"""Configuration for pytest."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.daybetter_services.const import CONF_TOKEN, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

SENSOR_PAYLOAD = [
    {
        "deviceId": "test_device_1",
        "deviceName": "test_sensor",
        "deviceGroupName": "Test Group",
        "deviceMoldPid": "pid1",
        "temp": 225,
        "humi": 650,
        "battery": 82,
    }
]


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="DayBetter Services",
        data={CONF_TOKEN: "test_token_12345"},
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, request: pytest.FixtureRequest
) -> tuple[MockConfigEntry, AsyncMock, AsyncMock]:
    """Set up the DayBetter Services integration in Home Assistant."""
    param = getattr(request, "param", None)
    payload = (param.get("payload") if param else SENSOR_PAYLOAD) or []
    fetch_kwargs: dict[str, Any]
    if param and (side_effect := param.get("side_effect")) is not None:
        fetch_kwargs = {"side_effect": side_effect}
    else:
        fetch_kwargs = {"return_value": deepcopy(payload)}

    with (
        patch(
            "homeassistant.components.daybetter_services.coordinator.DayBetterClient.fetch_sensor_data",
            **fetch_kwargs,
        ) as mock_fetch,
        patch(
            "homeassistant.components.daybetter_services.coordinator.DayBetterClient.close",
            AsyncMock(),
        ) as mock_close,
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield config_entry, mock_fetch, mock_close
