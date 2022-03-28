"""Tests for the Samsung TV Integration."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.media_player.const import DOMAIN, SUPPORT_TURN_ON
from homeassistant.components.samsungtv.const import (
    CONF_ON_ACTION,
    CONF_SSDP_MAIN_TV_AGENT_LOCATION,
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    DOMAIN as SAMSUNGTV_DOMAIN,
    METHOD_WEBSOCKET,
    UPNP_SVC_MAIN_TV_AGENT,
    UPNP_SVC_RENDERING_CONTROL,
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

from .const import (
    MOCK_ENTRYDATA_WS,
    MOCK_SSDP_DATA_MAIN_TV_AGENT_ST,
    MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
    SAMPLE_DEVICE_INFO_UE48JU6400,
)

from tests.common import MockConfigEntry

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


@pytest.mark.usefixtures("remotews", "remoteencws_failing", "rest_api")
async def test_setup(hass: HomeAssistant) -> None:
    """Test Samsung TV integration is setup."""
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)

    # test name and turn_on
    assert state
    assert state.name == "fake_name"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
    )

    # test host and port
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )


async def test_setup_from_yaml_without_port_device_offline(hass: HomeAssistant) -> None:
    """Test import from yaml when the device is offline."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote.start_listening",
        side_effect=OSError,
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
        side_effect=OSError,
    ), patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
        return_value=None,
    ):
        await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()

    config_entries_domain = hass.config_entries.async_entries(SAMSUNGTV_DOMAIN)
    assert len(config_entries_domain) == 1
    assert config_entries_domain[0].state == ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("remotews", "remoteencws_failing", "rest_api")
async def test_setup_from_yaml_without_port_device_online(hass: HomeAssistant) -> None:
    """Test import from yaml when the device is online."""
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()

    config_entries_domain = hass.config_entries.async_entries(SAMSUNGTV_DOMAIN)
    assert len(config_entries_domain) == 1
    assert config_entries_domain[0].data[CONF_MAC] == "aa:bb:ww:ii:ff:ii"


@pytest.mark.usefixtures("remote")
async def test_setup_duplicate_config(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test duplicate setup of platform."""
    duplicate = {
        SAMSUNGTV_DOMAIN: [
            MOCK_CONFIG[SAMSUNGTV_DOMAIN][0],
            MOCK_CONFIG[SAMSUNGTV_DOMAIN][0],
        ]
    }
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, duplicate)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is None
    assert len(hass.states.async_all("media_player")) == 0
    assert "duplicate host entries found" in caplog.text


@pytest.mark.usefixtures("remotews", "remoteencws_failing", "rest_api")
async def test_setup_duplicate_entries(hass: HomeAssistant) -> None:
    """Test duplicate setup of platform."""
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID)
    assert len(hass.states.async_all("media_player")) == 1
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
    assert len(hass.states.async_all("media_player")) == 1


@pytest.mark.usefixtures("remotews", "remoteencws_failing")
async def test_setup_h_j_model(
    hass: HomeAssistant, rest_api: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test Samsung TV integration is setup."""
    rest_api.rest_device_info.return_value = SAMPLE_DEVICE_INFO_UE48JU6400
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert "H and J series use an encrypted protocol" in caplog.text


@pytest.mark.usefixtures("remotews", "remoteencws_failing", "rest_api")
async def test_setup_updates_from_ssdp(hass: HomeAssistant) -> None:
    """Test setting up the entry fetches data from ssdp cache."""
    entry = MockConfigEntry(domain="samsungtv", data=MOCK_ENTRYDATA_WS)
    entry.add_to_hass(hass)

    async def _mock_async_get_discovery_info_by_st(hass: HomeAssistant, mock_st: str):
        if mock_st == UPNP_SVC_RENDERING_CONTROL:
            return [MOCK_SSDP_DATA_RENDERING_CONTROL_ST]
        if mock_st == UPNP_SVC_MAIN_TV_AGENT:
            return [MOCK_SSDP_DATA_MAIN_TV_AGENT_ST]
        raise ValueError(f"Unknown st {mock_st}")

    with patch(
        "homeassistant.components.samsungtv.ssdp.async_get_discovery_info_by_st",
        _mock_async_get_discovery_info_by_st,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert hass.states.get("media_player.any")
    assert (
        entry.data[CONF_SSDP_MAIN_TV_AGENT_LOCATION]
        == "https://fake_host:12345/tv_agent"
    )
    assert (
        entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION]
        == "https://fake_host:12345/test"
    )
