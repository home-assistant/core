"""Tests for the Samsung TV Integration."""
from asynctest import mock
from asynctest.mock import call, patch
import pytest

from homeassistant.components.media_player.const import DOMAIN, SUPPORT_TURN_ON
from homeassistant.components.samsungtv.const import (
    CONF_ON_ACTION,
    DOMAIN as SAMSUNGTV_DOMAIN,
)
from homeassistant.components.samsungtv.media_player import SUPPORT_SAMSUNGTV
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_NAME,
    SERVICE_VOLUME_UP,
)
from homeassistant.setup import async_setup_component

ENTITY_ID = f"{DOMAIN}.fake_name"
MOCK_CONFIG = {
    SAMSUNGTV_DOMAIN: [
        {
            CONF_HOST: "fake_host",
            CONF_NAME: "fake_name",
            CONF_ON_ACTION: [{"delay": "00:00:01"}],
        }
    ]
}
REMOTE_CALL = {
    "name": "HomeAssistant",
    "description": "HomeAssistant",
    "id": "ha.component.samsung",
    "method": "legacy",
    "host": MOCK_CONFIG[SAMSUNGTV_DOMAIN][0][CONF_HOST],
    "port": None,
    "timeout": 1,
}


@pytest.fixture(name="remote")
def remote_fixture():
    """Patch the samsungctl Remote."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote"
    ) as remote_class, patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ) as socket1, patch(
        "homeassistant.components.samsungtv.socket"
    ) as socket2:
        remote = mock.Mock()
        remote.__enter__ = mock.Mock()
        remote.__exit__ = mock.Mock()
        remote_class.return_value = remote
        socket1.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        socket2.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        yield remote


async def test_setup(hass, remote):
    """Test Samsung TV integration is setup."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
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
        assert remote.call_args == call(REMOTE_CALL)


async def test_setup_duplicate_config(hass, remote, caplog):
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
    assert len(hass.states.async_all()) == 0
    assert "duplicate host entries found" in caplog.text


async def test_setup_duplicate_entries(hass, remote, caplog):
    """Test duplicate setup of platform."""
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID)
    assert len(hass.states.async_all()) == 1
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
    assert len(hass.states.async_all()) == 1
