"""Tests for the Samsung TV Integration."""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.samsungtv.const import (
    CONF_SESSION_ID,
    CONF_SSDP_MAIN_TV_AGENT_LOCATION,
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    DOMAIN,
    METHOD_ENCRYPTED_WEBSOCKET,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
    UPNP_SVC_MAIN_TV_AGENT,
    UPNP_SVC_RENDERING_CONTROL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_samsungtv_entry
from .const import (
    ENTRYDATA_ENCRYPTED_WEBSOCKET,
    ENTRYDATA_LEGACY,
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


@pytest.mark.parametrize(
    "entry_data",
    [ENTRYDATA_LEGACY, ENTRYDATA_ENCRYPTED_WEBSOCKET, ENTRYDATA_WEBSOCKET],
    ids=[METHOD_LEGACY, METHOD_ENCRYPTED_WEBSOCKET, METHOD_WEBSOCKET],
)
@pytest.mark.usefixtures(
    "remote_encrypted_websocket",
    "remote_legacy",
    "remote_websocket",
    "rest_api_failing",
)
async def test_setup(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Samsung TV integration loads and fill device registry."""
    entry = await setup_samsungtv_entry(hass, entry_data)

    assert entry.state is ConfigEntryState.LOADED

    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert device_entries == snapshot


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
    # Introduced in #110599, can be removed in 2026.3
    await setup_samsungtv_entry(
        hass,
        {**ENTRYDATA_WEBSOCKET, CONF_MAC: "aabbaaaaaaaa"},
    )
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"
