"""Tests for the homelink integration."""

from typing import Any
from unittest.mock import AsyncMock

import jwt

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_UNIQUE_ID = "06ebba97-100b-4c09-9917-e85d40b7898a"
TEST_CREDENTIALS = {CONF_EMAIL: "test@test.com", CONF_PASSWORD: "SomePassword"}
TEST_ACCESS_JWT = jwt.encode({"sub": TEST_UNIQUE_ID}, key="secret")

INVALID_TEST_UNIQUE_ID = "0839246e-eb26-11f0-895d-325096b39f47"
INVALID_TEST_CREDENTIALS = {
    CONF_EMAIL: "invalid@invalid.com",
    CONF_PASSWORD: "InvalidPassword",
}
INVALID_TEST_ACCESS_JWT = jwt.encode({"sub": INVALID_TEST_UNIQUE_ID}, key="secret")


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the homelink integration for testing."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def update_callback(
    hass: HomeAssistant, mock: AsyncMock, update_type: str, data: dict[str, Any]
) -> None:
    """Invoke the MQTT provider's message callback with the specified update type and data."""
    for call in mock.listen.call_args_list:
        call[0][0](
            "topic",
            {
                "type": update_type,
                "data": data,
            },
        )

    await hass.async_block_till_done()
    await hass.async_block_till_done()
