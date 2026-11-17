"""Tests for the Samsung TV Integration."""

from datetime import timedelta
from typing import Any
from unittest.mock import Mock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

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
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_samsungtv_entry
from .const import (
    ENTRYDATA_ENCRYPTED_WEBSOCKET,
    ENTRYDATA_LEGACY,
    ENTRYDATA_WEBSOCKET,
    MOCK_SSDP_DATA_MAIN_TV_AGENT_ST,
    MOCK_SSDP_DATA_RENDERING_CONTROL_ST,
)


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


@pytest.mark.usefixtures("remote_websocket")
async def test_setup_h_j_model(
    hass: HomeAssistant, rest_api: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test Samsung TV integration is setup."""
    rest_api.rest_device_info.return_value = await async_load_json_object_fixture(
        hass, "device_info_UE48JU6400.json", DOMAIN
    )
    entry = await setup_samsungtv_entry(
        hass, {**ENTRYDATA_WEBSOCKET, CONF_MODEL: "UE48JU6400"}
    )

    assert entry.state is ConfigEntryState.LOADED

    assert "H and J series use an encrypted protocol" in caplog.text


@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_setup_updates_from_ssdp(hass: HomeAssistant) -> None:
    """Test setting up the entry fetches data from ssdp cache."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRYDATA_WEBSOCKET, entry_id="sample-entry-id"
    )
    entry.add_to_hass(hass)

    assert not entry.data.get(CONF_SSDP_MAIN_TV_AGENT_LOCATION)
    assert not entry.data.get(CONF_SSDP_RENDERING_CONTROL_LOCATION)

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

    assert (
        entry.data[CONF_SSDP_MAIN_TV_AGENT_LOCATION] == "http://10.10.12.34:7676/smp_2_"
    )
    assert (
        entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION]
        == "http://10.10.12.34:7676/smp_15_"
    )


@pytest.mark.parametrize(
    ("status", "text", "expected"),
    [
        (200, UPNP_SVC_RENDERING_CONTROL, "http://10.10.12.34:9197/dmr"),
        (404, "", None),
    ],
)
@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_setup_rendering_control_fallback(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    text: str,
    expected: str | None,
) -> None:
    """Test the renderer location is probed when ssdp has no data."""
    aioclient_mock.clear_requests()
    aioclient_mock.get("http://10.10.12.34:9197/dmr", status=status, text=text)
    entry = await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert entry.data.get(CONF_SSDP_RENDERING_CONTROL_LOCATION) == expected


@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_rendering_control_probe_on_power_on(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the renderer location is probed again when the TV turns on."""
    aioclient_mock.clear_requests()
    aioclient_mock.get("http://10.10.12.34:9197/dmr", exc=aiohttp.ClientError)
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_is_on",
        return_value=False,
    ) as mock_is_on:
        entry = await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)
        assert not entry.data.get(CONF_SSDP_RENDERING_CONTROL_LOCATION)

        aioclient_mock.clear_requests()
        aioclient_mock.get(
            "http://10.10.12.34:9197/dmr", text=UPNP_SVC_RENDERING_CONTROL
        )
        mock_is_on.return_value = True
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert (
            entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION]
            == "http://10.10.12.34:9197/dmr"
        )

        # Let the entry reload triggered by the update finish
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_rendering_control_probe_keeps_entry_updates(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entry updates made while probing on power on are kept."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSBridge.async_is_on",
        return_value=False,
    ) as mock_is_on:
        entry = await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

        async def _probe(hass: HomeAssistant, host: str) -> str:
            # The entry is updated (e.g. a new token) while the probe is running
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, "updated_during_probe": True}
            )
            return "http://10.10.12.34:9197/dmr"

        mock_is_on.return_value = True
        with patch(
            "homeassistant.components.samsungtv.coordinator."
            "async_probe_rendering_control_location",
            side_effect=_probe,
        ):
            freezer.tick(timedelta(seconds=10))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

        assert entry.data["updated_during_probe"] is True
        assert (
            entry.data[CONF_SSDP_RENDERING_CONTROL_LOCATION]
            == "http://10.10.12.34:9197/dmr"
        )

        # Let the entry reload triggered by the updates finish
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)


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
    # Incorrect MAC cleanup introduced in #110599, can be removed in 2026.3
    await setup_samsungtv_entry(
        hass,
        {**ENTRYDATA_WEBSOCKET, CONF_MAC: "aabbaaaaaaaa"},
    )
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"


async def test_migrate_future_version_returns_false(
    hass: HomeAssistant,
) -> None:
    """Test migration failure for downgraded future config entry version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRYDATA_WEBSOCKET,
        entry_id="sample-entry-id",
        version=3,
        minor_version=0,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
