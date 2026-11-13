"""Test setting up Voice support and asking for the app."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import ANY, AsyncMock, call, patch

from aiohasupervisor import SupervisorError
import aiohttp
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.voice_support import (
    DATA_CLIENT,
    INFO_REFRESH_INTERVAL,
    PREVIEW_FEATURE_NEXT_GENERATION_VOICE,
    AudioRunRequest,
    async_start_run,
)
from homeassistant.components.voice_support.client import AppInfo
from homeassistant.components.voice_support.const import (
    CONF_INTEGRATION_CREATED_APP,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_SYSTEM, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import APP_HOST, INFO, INFO_URL, PORT


async def test_setup_entry(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test setup connects to the app and unload removes the client."""
    assert setup_integration.state is ConfigEntryState.LOADED
    assert hass.data[DATA_CLIENT].info is not None

    await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    assert DATA_CLIENT not in hass.data


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        pytest.param({"exc": aiohttp.ClientError}, "cannot_connect", id="unreachable"),
        pytest.param({"json": {"name": "Voice"}}, "cannot_connect", id="malformed"),
        pytest.param(
            {"json": {**INFO, "api_version": 2}}, "unsupported_version", id="version"
        ),
    ],
)
async def test_setup_entry_cannot_use_app(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    reason: str,
) -> None:
    """Test an app that does not answer, or cannot be used, leaves the entry retrying."""
    aioclient_mock.get(INFO_URL, **response)
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == reason


async def test_info_refresh(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test app information is refreshed until the entry unloads."""
    client = hass.data[DATA_CLIENT]
    assert aioclient_mock.call_count == 1

    async_fire_time_changed(hass, dt_util.utcnow() + INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2
    assert client.info is not None

    await hass.config_entries.async_unload(setup_integration.entry_id)
    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=INFO)
    async_fire_time_changed(hass, dt_util.utcnow() + 2 * INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        pytest.param({"exc": aiohttp.ClientError}, "cannot_connect", id="unreachable"),
        pytest.param({"json": {"name": "Voice"}}, "cannot_connect", id="malformed"),
        pytest.param(
            {"json": {**INFO, "api_version": 2}}, "unsupported_version", id="version"
        ),
    ],
)
async def test_info_refresh_reloads_unusable_app(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    reason: str,
) -> None:
    """Test an unusable app reloads the entry and recovers through setup retries."""
    client = hass.data[DATA_CLIENT]
    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, **response)

    async_fire_time_changed(hass, dt_util.utcnow() + INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()

    assert client.info is None
    assert DATA_CLIENT not in hass.data
    assert setup_integration.state is ConfigEntryState.SETUP_RETRY
    assert setup_integration.error_reason_translation_key == reason

    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=INFO)
    async_fire_time_changed(hass, dt_util.utcnow() + 2 * INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.LOADED
    assert hass.data[DATA_CLIENT].info is not None


@pytest.mark.parametrize(
    ("owned", "api_version", "update_available", "update_error", "expected_updates"),
    [
        pytest.param(True, 0, True, None, 1, id="owned_outdated"),
        pytest.param(True, 0, False, None, 0, id="no_update"),
        pytest.param(False, 0, True, None, 0, id="external"),
        pytest.param(True, 2, True, None, 1, id="newer_protocol"),
        pytest.param(True, 0, True, SupervisorError("busy"), 1, id="update_failed"),
    ],
)
@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_setup_updates_owned_app(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    addon_info: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
    owned: bool,
    api_version: int,
    update_available: bool,
    update_error: Exception | None,
    expected_updates: int,
) -> None:
    """Test setup updates an incompatible app only when the integration installed it."""
    addon_info.return_value.update_available = update_available
    update_addon.side_effect = update_error
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_INTEGRATION_CREATED_APP: owned},
    )
    aioclient_mock.get(INFO_URL, json={**INFO, "api_version": api_version})

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert create_backup.call_count == expected_updates
    assert update_addon.call_count == expected_updates


SYSTEM_FLOW = call(ANY, DOMAIN, context={"source": SOURCE_SYSTEM}, data={})


@pytest.mark.parametrize(
    ("components", "feature", "expected_flows"),
    [
        pytest.param(set(), True, [], id="no_supervisor"),
        pytest.param({"hassio"}, False, [], id="feature_off"),
        pytest.param({"hassio"}, True, [SYSTEM_FLOW], id="wanted"),
    ],
)
@pytest.mark.usefixtures("labs")
async def test_loading_provisions(
    hass: HomeAssistant,
    components: set[str],
    feature: bool,
    expected_flows: list[Any],
) -> None:
    """Test loading asks for the app, on a Supervised system with the feature on."""
    hass.config.components.update(components)
    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, feature
    )

    with patch(
        "homeassistant.components.voice_support.discovery_flow.async_create_flow"
    ) as create_flow:
        assert await async_setup_component(hass, DOMAIN, {})

    assert create_flow.call_args_list == expected_flows


@pytest.mark.usefixtures("supervisor", "preview_feature_enabled")
async def test_provision_once(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an entry, or a flow already underway, means nothing more to do."""
    with patch(
        "homeassistant.components.voice_support.discovery_flow.async_create_flow"
    ) as create_flow:
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert await async_setup_component(hass, DOMAIN, {})
        assert create_flow.call_count == 0

        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
            hass.config_entries.flow.async_abort(flow["flow_id"])
        mock_config_entry.add_to_hass(hass)
        await async_update_preview_feature(
            hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, False
        )
        await async_update_preview_feature(
            hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, True
        )
        await hass.async_block_till_done()
        assert create_flow.call_count == 0


@pytest.mark.usefixtures("supervisor", "preview_feature_enabled")
async def test_enabling_the_feature_asks_for_the_app(hass: HomeAssistant) -> None:
    """Test turning the feature on is one of the moments the app is wanted."""
    with patch(
        "homeassistant.components.voice_support.discovery_flow.async_create_flow"
    ) as create_flow:
        assert await async_setup_component(hass, DOMAIN, {})
        assert create_flow.call_count == 1

        await async_update_preview_feature(
            hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, False
        )
        await hass.async_block_till_done()
        assert create_flow.call_count == 1

        await async_update_preview_feature(
            hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, True
        )
        await hass.async_block_till_done()
        assert create_flow.call_count == 2


@pytest.mark.parametrize(
    ("owned", "expected_removals", "expected_refreshes"),
    [
        pytest.param(True, 1, 0, id="managed"),
        pytest.param(False, 0, 1, id="manual"),
    ],
)
@pytest.mark.usefixtures(
    "supervisor", "addon_running", "preview_feature_enabled", "app_info"
)
async def test_disabling_removes_managed_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    stop_addon: AsyncMock,
    create_backup: AsyncMock,
    uninstall_addon: AsyncMock,
    owned: bool,
    expected_removals: int,
    expected_refreshes: int,
) -> None:
    """Test disabling removes only entries and apps created by the integration."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_INTEGRATION_CREATED_APP: owned},
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, False
    )
    await hass.async_block_till_done()

    assert (
        hass.config_entries.async_get_entry(mock_config_entry.entry_id) is None
    ) == owned
    assert (DATA_CLIENT not in hass.data) == owned
    assert stop_addon.call_count == expected_removals
    assert create_backup.call_count == expected_removals
    assert uninstall_addon.call_count == expected_removals

    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=INFO)
    async_fire_time_changed(hass, dt_util.utcnow() + INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == expected_refreshes

    with patch(
        "homeassistant.components.voice_support.discovery_flow.async_create_flow"
    ) as create_flow:
        await async_update_preview_feature(
            hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, True
        )
        await hass.async_block_till_done()
        assert create_flow.call_count == expected_removals


@pytest.mark.parametrize("component", ["assist_pipeline", "assist_satellite"])
async def test_voice_component_loads_the_integration(
    hass: HomeAssistant, component: str
) -> None:
    """Test voice support loads through the pipeline dependency."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, component, {})

    assert DOMAIN in hass.config.components


@pytest.mark.parametrize(
    ("extra_data", "expected_calls"),
    [
        pytest.param({CONF_INTEGRATION_CREATED_APP: True}, 1, id="ours"),
        pytest.param({}, 0, id="theirs"),
    ],
)
@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_remove_entry(
    hass: HomeAssistant,
    stop_addon: AsyncMock,
    create_backup: AsyncMock,
    uninstall_addon: AsyncMock,
    extra_data: dict[str, Any],
    expected_calls: int,
) -> None:
    """Test removing the entry takes the app with it only if we installed it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Voice",
        data={CONF_HOST: APP_HOST, CONF_PORT: PORT, **extra_data},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert stop_addon.call_count == expected_calls
    assert create_backup.call_count == expected_calls
    assert uninstall_addon.call_count == expected_calls


@pytest.mark.usefixtures("supervisor", "addon_running", "create_backup")
async def test_remove_entry_app_error(
    hass: HomeAssistant,
    stop_addon: AsyncMock,
    uninstall_addon: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the app refusing to stop is logged, and the entry still goes."""
    stop_addon.side_effect = SupervisorError("busy")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Voice",
        data={CONF_HOST: APP_HOST, CONF_PORT: PORT, CONF_INTEGRATION_CREATED_APP: True},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert uninstall_addon.call_count == 0
    assert "Failed to stop the Voice app: busy" in caplog.text
    assert not hass.config_entries.async_entries(DOMAIN)


async def _no_audio() -> AsyncGenerator[bytes]:
    return
    yield


@pytest.mark.usefixtures("labs")
async def test_start_run_without_entry(hass: HomeAssistant) -> None:
    """Test there is no run to give before the integration loads, nor without an entry."""
    assert await async_start_run(hass, AudioRunRequest(), _no_audio()) is None

    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_start_run(hass, AudioRunRequest(), _no_audio()) is None


@pytest.mark.usefixtures("setup_integration")
async def test_start_run_gated_by_preview_feature(
    hass: HomeAssistant, labs: None
) -> None:
    """Test the pipeline gets no run while the feature is off."""
    client = hass.data[DATA_CLIENT]
    request = AudioRunRequest(wake_word_phrase="okay nabu")

    with patch.object(
        client, "async_start_run", new=AsyncMock(return_value="run")
    ) as start_run:
        assert await async_start_run(hass, request, _no_audio()) is None
        assert start_run.call_count == 0

        await async_update_preview_feature(
            hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, True
        )
        audio = _no_audio()
        assert await async_start_run(hass, request, audio) == "run"
        assert start_run.call_args[0] == (request, audio)


@pytest.mark.parametrize(
    ("owned", "update_available", "expected_updates"),
    [(True, True, 1), (True, False, 0), (False, True, 0)],
)
@pytest.mark.usefixtures("supervisor", "addon_running", "app_info")
async def test_setup_updates_compatible_app(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    addon_info: AsyncMock,
    update_addon: AsyncMock,
    owned: bool,
    update_available: bool,
    expected_updates: int,
) -> None:
    """Test compatible managed apps are also updated when an update is available."""
    addon_info.return_value.update_available = update_available
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_INTEGRATION_CREATED_APP: owned},
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert update_addon.call_count == expected_updates


@pytest.mark.usefixtures("supervisor", "addon_running", "app_info")
async def test_refresh_does_not_update_managed_app(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    addon_info: AsyncMock,
    update_addon: AsyncMock,
) -> None:
    """Test periodic info refreshes do not update the app."""
    addon_info.return_value.update_available = False
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_INTEGRATION_CREATED_APP: True},
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    update_addon.assert_not_called()

    addon_info.return_value.update_available = True
    async_fire_time_changed(hass, dt_util.utcnow() + INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()

    update_addon.assert_not_called()


async def test_setup_waits_for_info_before_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the app cannot update while the initial info request is pending."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_INTEGRATION_CREATED_APP: True},
    )
    info_requested = asyncio.Event()
    info: asyncio.Future[AppInfo] = asyncio.Future()

    async def async_read_info() -> AppInfo:
        info_requested.set()
        return await info

    with (
        patch(
            "homeassistant.components.voice_support.VoiceSupportClient.async_update_info",
            side_effect=async_read_info,
        ),
        patch("homeassistant.components.voice_support.get_app_manager") as app_manager,
    ):
        setup_task = hass.async_create_task(
            hass.config_entries.async_setup(mock_config_entry.entry_id)
        )
        await info_requested.wait()
        app_manager.assert_not_called()

        info.set_result(AppInfo.from_json(INFO))
        assert await setup_task

    app_manager.return_value.async_schedule_update_addon.assert_called_once_with(
        catch_error=True
    )
