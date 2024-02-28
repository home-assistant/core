"""Tests for the Webmin integration."""
from unittest.mock import patch

from homeassistant.components.webmin.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_USER_INPUT

from tests.common import MockConfigEntry, load_json_object_fixture


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""

    entry = MockConfigEntry(domain=DOMAIN, options=TEST_USER_INPUT, title="name")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.webmin.helpers.WebminInstance.update",
        return_value=load_json_object_fixture("webmin_update.json", DOMAIN),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
