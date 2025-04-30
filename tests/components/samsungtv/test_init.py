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
    CONF_MANUFACTURER,
    CONF_SESSION_ID,
    CONF_SSDP_MAIN_TV_AGENT_LOCATION,
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    DOMAIN,
    LEGACY_PORT,
    METHOD_LEGACY,
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
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_samsungtv_entry
from .const import (
    MOCK_ENTRY_WS_WITH_MAC,
    MOCK_ENTRYDATA_ENCRYPTED_WS,
    MOCK_ENTRYDATA_WS,
    MOCK_SSDP_DATA_MAIN_TV_AGENT_ST,
    MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
    SAMPLE_DEVICE_INFO_UE48JU6400,
)

from tests.common import MockConfigEntry

ENTITY_ID = f"{MP_DOMAIN}.fake_name"
MOCK_CONFIG = {
    CONF_HOST: "fake_host",
    CONF_NAME: "fake_name",
    CONF_METHOD: METHOD_WEBSOCKET,
}


@pytest.mark.usefixtures("remotews", "remoteencws_failing", "rest_api")
async def test_setup(hass: HomeAssistant) -> None:
    """Test Samsung TV integration is setup."""
    await setup_samsungtv_entry(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    # test name and turn_on
    assert state
    assert state.name == "fake_name"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == SUPPORT_SAMSUNGTV | MediaPlayerEntityFeature.TURN_ON
    )

    # test host and port
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )


async def test_setup_without_port_device_offline(hass: HomeAssistant) -> None:
    """Test import from yaml when the device is offline."""
    with (
        patch("homeassistant.components.samsungtv.bridge.Remote", side_effect=OSError),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote.start_listening",
            side_effect=OSError,
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote.open",
            side_effect=OSError,
        ),
        patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_device_info",
            return_value=None,
        ),
    ):
        await setup_samsungtv_entry(hass, MOCK_CONFIG)

    config_entries_domain = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries_domain) == 1
    assert config_entries_domain[0].state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("remotews", "remoteencws_failing", "rest_api")
async def test_setup_without_port_device_online(hass: HomeAssistant) -> None:
    """Test import from yaml when the device is online."""
    await setup_samsungtv_entry(hass, MOCK_CONFIG)

    config_entries_domain = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries_domain) == 1
    assert config_entries_domain[0].data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"


@pytest.mark.usefixtures("remotews", "remoteencws_failing")
async def test_setup_h_j_model(
    hass: HomeAssistant, rest_api: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test Samsung TV integration is setup."""
    rest_api.rest_device_info.return_value = SAMPLE_DEVICE_INFO_UE48JU6400
    await setup_samsungtv_entry(hass, MOCK_CONFIG)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert "H and J series use an encrypted protocol" in caplog.text


@pytest.mark.usefixtures("remotews", "remoteencws_failing", "rest_api")
async def test_setup_updates_from_ssdp(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setting up the entry fetches data from ssdp cache."""
    entry = MockConfigEntry(
        domain="samsungtv", data=MOCK_ENTRYDATA_WS, entry_id="sample-entry-id"
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

    assert hass.states.get("media_player.any") == snapshot
    assert entity_registry.async_get("media_player.any") == snapshot
    assert (
        entry.data[CONF_SSDP_MAIN_TV_AGENT_LOCATION]
        == "https://fake_host:12345/tv_agent"
    )
    assert (
        entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION]
        == "https://fake_host:12345/test"
    )


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_reauth_triggered_encrypted(hass: HomeAssistant) -> None:
    """Test reauth flow is triggered for encrypted TVs."""
    encrypted_entry_data = {**MOCK_ENTRYDATA_ENCRYPTED_WS}
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


@pytest.mark.usefixtures("remote", "remotews", "rest_api_failing")
async def test_update_imported_legacy_without_method(hass: HomeAssistant) -> None:
    """Test updating an imported legacy entry without a method."""
    await setup_samsungtv_entry(
        hass, {CONF_HOST: "fake_host", CONF_MANUFACTURER: "Samsung"}
    )

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_METHOD] == METHOD_LEGACY
    assert entries[0].data[CONF_PORT] == LEGACY_PORT


@pytest.mark.usefixtures("remotews", "rest_api")
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


@pytest.mark.usefixtures("remotews", "rest_api")
@pytest.mark.xfail
async def test_cleanup_mac(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test for `none` mac cleanup #103512.

    Reverted due to device registry collisions in #119249 / #119082
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_WS_WITH_MAC,
        entry_id="123456",
        unique_id="be9554b9-c9fb-41f4-8920-22da015376a4",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    # Setup initial device registry, with incorrect MAC
    device_registry.async_get_or_create(
        config_entry_id="123456",
        connections={
            (dr.CONNECTION_NETWORK_MAC, "none"),
            (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff"),
        },
        identifiers={("samsungtv", "be9554b9-c9fb-41f4-8920-22da015376a4")},
        model="82GXARRS",
        name="fake",
    )
    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert device_entries == snapshot
    assert device_entries[0].connections == {
        (dr.CONNECTION_NETWORK_MAC, "none"),
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff"),
    }

    # Run setup, and ensure the NONE mac is removed
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert device_entries == snapshot
    assert device_entries[0].connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }

    assert entry.version == 2
    assert entry.minor_version == 2
