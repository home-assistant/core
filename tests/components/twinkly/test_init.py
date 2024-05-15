"""Tests of the initialization of the twinly integration."""

from unittest.mock import patch
from uuid import uuid4

from homeassistant.components.twinkly.const import DOMAIN as TWINKLY_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant

from . import TEST_HOST, TEST_MODEL, TEST_NAME_ORIGINAL, ClientMock

from tests.common import MockConfigEntry


async def test_load_unload_entry(hass: HomeAssistant) -> None:
    """Validate that setup entry also configure the client."""
    client = ClientMock()

    device_id = str(uuid4())
    config_entry = MockConfigEntry(
        domain=TWINKLY_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_ID: device_id,
            CONF_NAME: TEST_NAME_ORIGINAL,
            CONF_MODEL: TEST_MODEL,
        },
        entry_id=device_id,
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.twinkly.Twinkly", return_value=client):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Validate that config entry is retried."""
    client = ClientMock()
    client.is_offline = True

    config_entry = MockConfigEntry(
        domain=TWINKLY_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_ID: id,
            CONF_NAME: TEST_NAME_ORIGINAL,
            CONF_MODEL: TEST_MODEL,
        },
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.twinkly.Twinkly", return_value=client):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
