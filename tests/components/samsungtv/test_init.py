"""Tests for the Samsung TV Integration."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from samsungtvws.async_remote import SamsungTVWSAsyncRemote
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    MediaPlayerEntityFeature,
)
from homeassistant.components.samsungtv.const import (
    CONF_SESSION_ID,
    CONF_SSDP_MAIN_TV_AGENT_LOCATION,
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    DOMAIN,
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
    CONF_PORT,
    CONF_TOKEN,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_samsungtv_entry
from .const import (
    ENTRYDATA_ENCRYPTED_WEBSOCKET,
    ENTRYDATA_WEBSOCKET,
    MOCK_SSDP_DATA_MAIN_TV_AGENT_ST,
    MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
)

from tests.common import MockConfigEntry, load_json_object_fixture

ENTITY_ID = f"{MP_DOMAIN}.mock_title"
MOCK_CONFIG = {
    CONF_HOST: "fake_host",
    CONF_NAME: "fake_name",
    CONF_METHOD: METHOD_WEBSOCKET,
    CONF_PORT: 8001,
}


@pytest.mark.usefixtures(
    "remote_websocket", "remote_encrypted_websocket_failing", "rest_api"
)
async def test_setup(hass: HomeAssistant) -> None:
    """Test Samsung TV integration is setup."""
    await setup_samsungtv_entry(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    # test name and turn_on
    assert state
    assert state.name == "Mock Title"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == SUPPORT_SAMSUNGTV | MediaPlayerEntityFeature.TURN_ON
    )

    # Ensure service is registered
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )


@pytest.mark.usefixtures("remote_websocket", "remote_encrypted_websocket_failing")
async def test_setup_h_j_model(
    hass: HomeAssistant, rest_api: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test Samsung TV integration is setup."""
    rest_api.rest_device_info.return_value = load_json_object_fixture(
        "device_info_UE48JU6400.json", DOMAIN
    )
    await setup_samsungtv_entry(hass, MOCK_CONFIG)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert "H and J series use an encrypted protocol" in caplog.text


@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_setup_updates_from_ssdp(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setting up the entry fetches data from ssdp cache."""
    entry = MockConfigEntry(
        domain="samsungtv", data=ENTRYDATA_WEBSOCKET, entry_id="sample-entry-id"
    )
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

    assert hass.states.get("media_player.mock_title") == snapshot
    assert entity_registry.async_get("media_player.mock_title") == snapshot
    assert (
        entry.data[CONF_SSDP_MAIN_TV_AGENT_LOCATION] == "http://10.10.12.34:7676/smp_2_"
    )
    assert (
        entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION]
        == "http://10.10.12.34:7676/smp_15_"
    )


@pytest.mark.usefixtures("remote_encrypted_websocket", "rest_api")
async def test_reauth_triggered_encrypted(hass: HomeAssistant) -> None:
    """Test reauth flow is triggered for encrypted TVs."""
    encrypted_entry_data = {**ENTRYDATA_ENCRYPTED_WEBSOCKET}
    del encrypted_entry_data[CONF_TOKEN]
    del encrypted_entry_data[CONF_SESSION_ID]

    entry = await setup_samsungtv_entry(hass, encrypted_entry_data)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows_in_progress = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert len(flows_in_progress) == 1


@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_incorrectly_formatted_mac_fixed(hass: HomeAssistant) -> None:
    """Test incorrectly formatted mac is corrected."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote"
    ) as remote_class:
        remote = Mock(SamsungTVWSAsyncRemote)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock()
        remote.token = "123456789"
        remote_class.return_value = remote

        await setup_samsungtv_entry(
            hass,
            {
                CONF_HOST: "fake_host",
                CONF_NAME: "fake",
                CONF_PORT: 8001,
                CONF_TOKEN: "123456789",
                CONF_METHOD: METHOD_WEBSOCKET,
                CONF_MAC: "aabbaaaaaaaa",
            },
        )
        await hass.async_block_till_done()

        config_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries) == 1
        assert config_entries[0].data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
