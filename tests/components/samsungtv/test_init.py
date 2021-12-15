"""Tests for the Samsung TV Integration."""
from unittest.mock import Mock, patch

from homeassistant.components.media_player.const import DOMAIN, SUPPORT_TURN_ON
from homeassistant.components.samsungtv.const import (
    CONF_ON_ACTION,
    DOMAIN as SAMSUNGTV_DOMAIN,
    METHOD_WEBSOCKET,
)
from homeassistant.components.samsungtv.media_player import SUPPORT_SAMSUNGTV
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_ID = f"{DOMAIN}.fake_name"
MOCK_CONFIG = {
    SAMSUNGTV_DOMAIN: [
        {
            CONF_HOST: "fake_host",
            CONF_NAME: "fake_name",
            CONF_ON_ACTION: [{"delay": "00:00:01"}],
            CONF_METHOD: METHOD_WEBSOCKET,
        }
    ]
}
MOCK_CONFIG_WITHOUT_PORT = {
    SAMSUNGTV_DOMAIN: [
        {
            CONF_HOST: "fake_host",
            CONF_NAME: "fake",
            CONF_ON_ACTION: [{"delay": "00:00:01"}],
        }
    ]
}

REMOTE_CALL = {
    "name": "HomeAssistant",
    "description": "HomeAssistant",
    "id": "ha.component.samsung",
    "host": MOCK_CONFIG[SAMSUNGTV_DOMAIN][0][CONF_HOST],
    "method": "legacy",
    "port": None,
    "timeout": 1,
}


async def test_setup(hass: HomeAssistant, remotews: Mock, no_mac_address: Mock):
    """Test Samsung TV integration is setup."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):

        await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_ID)

        # test name and turn_on
        assert state
        assert state.name == "fake_name"
        assert (
            state.attributes[ATTR_SUPPORTED_FEATURES]
            == SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
        )

        # test host and port
        assert await hass.services.async_call(
            DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
        )


async def test_setup_from_yaml_without_port_device_offline(hass: HomeAssistant):
    """Test import from yaml when the device is offline."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS.open",
        side_effect=OSError,
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.device_info",
        return_value=None,
    ), patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()

    config_entries_domain = hass.config_entries.async_entries(SAMSUNGTV_DOMAIN)
    assert len(config_entries_domain) == 1
    assert config_entries_domain[0].state == ConfigEntryState.SETUP_RETRY


async def test_setup_from_yaml_without_port_device_online(
    hass: HomeAssistant, remotews: Mock
):
    """Test import from yaml when the device is online."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()

    config_entries_domain = hass.config_entries.async_entries(SAMSUNGTV_DOMAIN)
    assert len(config_entries_domain) == 1
    assert config_entries_domain[0].data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"


async def test_setup_duplicate_config(hass: HomeAssistant, remote: Mock, caplog):
    """Test duplicate setup of platform."""
    DUPLICATE = {
        SAMSUNGTV_DOMAIN: [
            MOCK_CONFIG[SAMSUNGTV_DOMAIN][0],
            MOCK_CONFIG[SAMSUNGTV_DOMAIN][0],
        ]
    }
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, DUPLICATE)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is None
    assert len(hass.states.async_all("media_player")) == 0
    assert "duplicate host entries found" in caplog.text


async def test_setup_duplicate_entries(
    hass: HomeAssistant, remote: Mock, remotews: Mock, no_mac_address: Mock, caplog
):
    """Test duplicate setup of platform."""
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID)
    assert len(hass.states.async_all("media_player")) == 1
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
    assert len(hass.states.async_all("media_player")) == 1
