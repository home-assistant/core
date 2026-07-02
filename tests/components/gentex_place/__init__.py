"""Tests for the gentex_place integration."""

from unittest.mock import MagicMock

import jwt

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_UNIQUE_ID = "06ebba97-100b-4c09-9917-e85d40b7898a"
TEST_CREDENTIALS = {CONF_EMAIL: "test@test.com", CONF_PASSWORD: "SomePassword"}
TEST_ACCESS_JWT = jwt.encode({"sub": TEST_UNIQUE_ID}, key="secret")

INVALID_TEST_UNIQUE_ID = "0839246e-eb26-11f0-895d-325096b39f47"
INVALID_TEST_ACCESS_JWT = jwt.encode({"sub": INVALID_TEST_UNIQUE_ID}, key="secret")


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the gentex_place integration for testing."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def trigger_shadow_callback(
    mock_mqtt_client: MagicMock,
    topic: str,
    payload: bytes,
) -> None:
    """Invoke the MQTT client's on_message callback."""
    on_message = mock_mqtt_client.connect.call_args.kwargs["on_message"]
    on_message(topic, payload)


def trigger_mqtt_connect(mock_mqtt_client: MagicMock) -> None:
    """Invoke the MQTT client's on_connect callback."""
    mock_mqtt_client.connect.call_args.kwargs["on_connect"]()
