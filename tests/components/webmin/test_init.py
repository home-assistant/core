"""Tests for the Webmin integration."""
from unittest.mock import patch

from homeassistant.components.webmin.const import DOMAIN
from homeassistant.components.webmin.coordinator import WebminUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_USER_INPUT_REQUIRED

from tests.common import MockConfigEntry, load_json_object_fixture

# pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    with patch(
        "webmin_xmlrpc.client.WebminInstance.update",
        return_value=load_json_object_fixture("webmin_update.json", DOMAIN),
    ), patch(
        "webmin_xmlrpc.client.WebminInstance.get_network_interfaces",
        return_value=load_json_object_fixture("webmin_network_interfaces.json", DOMAIN),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN, options=TEST_USER_INPUT_REQUIRED, title="name"
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert isinstance(hass.data[DOMAIN][entry.entry_id], WebminUpdateCoordinator)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
