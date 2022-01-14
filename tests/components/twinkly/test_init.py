"""Tests of the initialization of the twinly integration."""

from unittest.mock import patch
from uuid import uuid4

from homeassistant.components.twinkly.const import (
    DOMAIN as TWINKLY_DOMAIN,
    ENTRY_DATA_HOST,
    ENTRY_DATA_ID,
    ENTRY_DATA_MODEL,
    ENTRY_DATA_NAME,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.twinkly import (
    TEST_HOST,
    TEST_MODEL,
    TEST_NAME_ORIGINAL,
    ClientMock,
)


async def test_load_unload_entry(hass: HomeAssistant):
    """Validate that setup entry also configure the client."""
    client = ClientMock()

    id = str(uuid4())
    config_entry = MockConfigEntry(
        domain=TWINKLY_DOMAIN,
        data={
            ENTRY_DATA_HOST: TEST_HOST,
            ENTRY_DATA_ID: id,
            ENTRY_DATA_NAME: TEST_NAME_ORIGINAL,
            ENTRY_DATA_MODEL: TEST_MODEL,
        },
        entry_id=id,
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.twinkly.Twinkly", return_value=client):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(hass: HomeAssistant):
    """Validate that config entry is retried."""
    client = ClientMock()
    client.is_offline = True

    config_entry = MockConfigEntry(
        domain=TWINKLY_DOMAIN,
        data={
            ENTRY_DATA_HOST: TEST_HOST,
            ENTRY_DATA_ID: id,
            ENTRY_DATA_NAME: TEST_NAME_ORIGINAL,
            ENTRY_DATA_MODEL: TEST_MODEL,
        },
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.twinkly.Twinkly", return_value=client):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
