"""Tests for the AVM Fritz!Box Integration."""
from unittest.mock import Mock, call, patch

import pytest

from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

ENTITY_ID = f"{SWITCH_DOMAIN}.fritzbox"
MOCK_CONFIG = {
    FB_DOMAIN: [
        {
            CONF_HOST: "fake_host",
            CONF_PASSWORD: "fake_pass",
            CONF_USERNAME: "fake_user",
        }
    ]
}


@pytest.fixture(name="fritz")
def fritz_fixture():
    """Patch libraries."""
    with patch("homeassistant.components.fritzbox.socket") as socket1, patch(
        "homeassistant.components.fritzbox.config_flow.socket"
    ) as socket2, patch("homeassistant.components.fritzbox.Fritzhome") as fritz, patch(
        "homeassistant.components.fritzbox.config_flow.Fritzhome"
    ):
        socket1.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        socket2.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        yield fritz


async def test_setup(hass: HomeAssistantType, fritz: Mock):
    """Test setup of integration."""
    await async_setup_component(hass, FB_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries()
    assert entries
    assert entries[0].data[CONF_HOST] == "fake_host"
    assert entries[0].data[CONF_PASSWORD] == "fake_pass"
    assert entries[0].data[CONF_USERNAME] == "fake_user"
    assert fritz.call_count == 1
    assert fritz.call_args_list == [
        call(host="fake_host", password="fake_pass", user="fake_user")
    ]


async def test_setup_duplicate_config(hass: HomeAssistantType, fritz: Mock, caplog):
    """Test duplicate config of integration."""
    DUPLICATE = {FB_DOMAIN: [MOCK_CONFIG[FB_DOMAIN][0], MOCK_CONFIG[FB_DOMAIN][0]]}
    await async_setup_component(hass, FB_DOMAIN, DUPLICATE)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is None
    assert len(hass.states.async_all()) == 0
    assert "duplicate host entries found" in caplog.text


async def test_setup_duplicate_entries(hass: HomeAssistantType, fritz: Mock):
    """Test duplicate setup of integration."""
    await async_setup_component(hass, FB_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries()) == 1
    await async_setup_component(hass, FB_DOMAIN, MOCK_CONFIG)
    assert len(hass.config_entries.async_entries()) == 1


async def test_unload(hass: HomeAssistantType, fritz: Mock):
    """Test unload of integration."""
    await async_setup_component(hass, FB_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    # how to call unloading?
    assert fritz.logout.call_count >= 1
