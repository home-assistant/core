"""Tests for the Samsung TV Integration."""
import pytest
from unittest.mock import call, patch

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    SERVICE_VOLUME_UP,
)
from homeassistant.components.media_player.const import DOMAIN, SUPPORT_TURN_ON
from homeassistant.components import samsungtv
from homeassistant.components.samsungtv.const import DOMAIN as SAMSUNGTV_DOMAIN
from homeassistant.components.samsungtv.media_player import SUPPORT_SAMSUNGTV

ENTITY_ID = f"{DOMAIN}.fake_name"
MOCK_CONFIG = {
    SAMSUNGTV_DOMAIN: [
        {
            CONF_HOST: "fake_host",
            CONF_MAC: "fake_mac",
            CONF_NAME: "fake_name",
            CONF_PORT: 1234,
            CONF_TIMEOUT: 999,
        }
    ]
}
REMOTE_CALL = {
    "name": "HomeAssistant",
    "description": MOCK_CONFIG[SAMSUNGTV_DOMAIN][0][CONF_NAME],
    "id": "ha.component.samsung",
    "method": "websocket",
    "port": MOCK_CONFIG[SAMSUNGTV_DOMAIN][0][CONF_PORT],
    "host": MOCK_CONFIG[SAMSUNGTV_DOMAIN][0][CONF_HOST],
    "timeout": MOCK_CONFIG[SAMSUNGTV_DOMAIN][0][CONF_TIMEOUT],
}


@pytest.fixture(name="remote")
def remote_fixture():
    """Patch the samsungctl Remote."""
    with patch("homeassistant.components.samsungtv.config_flow.socket"), patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote"
    ) as remote, patch("homeassistant.components.samsungtv.media_player.socket"):
        yield remote


async def test_setup(hass, remote):
    """Test Samsung TV integration is setup."""
    await samsungtv.async_setup(hass, MOCK_CONFIG)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)

    # test name and mac
    assert state
    assert state.name == "fake_name"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
    )

    # test host, port and timeout
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert remote.mock_calls[0] == call(REMOTE_CALL)
