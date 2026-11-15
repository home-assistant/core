"""Test setting up Voice support and asking for the app."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock, call, patch

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import AddonState as SupervisorAddonState
import aiohttp
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.hassio import AddonState
from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.voice_support import (
    DATA_CLIENT,
    INFO_REFRESH_INTERVAL,
    PREVIEW_FEATURE_NEXT_GENERATION_VOICE,
    AudioRunRequest,
    async_on_wake_words_changed,
    async_start_run,
    async_verifies_wake_word,
)
from homeassistant.components.voice_support.app import APP_SLUG
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
    ("owned", "state", "expected_starts"),
    [
        pytest.param(True, SupervisorAddonState.STOPPED, 1, id="stopped"),
        pytest.param(True, SupervisorAddonState.STARTED, 0, id="running"),
        pytest.param(False, SupervisorAddonState.STOPPED, 0, id="external"),
    ],
)
@pytest.mark.usefixtures("supervisor", "addon_installed", "app_info")
async def test_setup_starts_owned_app(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    addon_info: AsyncMock,
    start_addon: AsyncMock,
    owned: bool,
    state: SupervisorAddonState,
    expected_starts: int,
) -> None:
    """Test a stopped managed app starts before the first connection."""
    addon_info.return_value.state = state

    async def async_start(slug: str) -> None:
        assert slug == APP_SLUG
        assert aioclient_mock.call_count == 0
        await asyncio.sleep(0)
        assert aioclient_mock.call_count == 0

    start_addon.side_effect = async_start
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_INTEGRATION_CREATED_APP: owned},
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert start_addon.await_count == expected_starts
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize("failed_operation", ["info", "start"])
@pytest.mark.usefixtures("supervisor", "addon_installed", "app_info")
async def test_setup_retries_app_start_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    addon_info: AsyncMock,
    start_addon: AsyncMock,
    failed_operation: str,
) -> None:
    """Test Supervisor failures leave setup retrying without connecting."""
    operations = {"info": addon_info, "start": start_addon}
    operations[failed_operation].side_effect = SupervisorError("busy")
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_INTEGRATION_CREATED_APP: True},
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
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


@pytest.mark.usefixtures("labs", "app_info")
async def test_verifies_wake_word(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a wake word is verified only with the feature on and an app that has it."""
    assert await async_setup_component(hass, DOMAIN, {})
    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, True
    )
    assert not async_verifies_wake_word(hass, "Okay Nabu")

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert async_verifies_wake_word(hass, "Okay Nabu")
    assert not async_verifies_wake_word(hass, "Hey Jarvis")

    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, False
    )
    await hass.async_block_till_done()
    assert not async_verifies_wake_word(hass, "Okay Nabu")


@pytest.mark.usefixtures("labs", "app_info")
async def test_wake_words_changed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test listeners hear when the app comes and goes and the feature changes."""
    assert await async_setup_component(hass, DOMAIN, {})
    listener = Mock()
    remove_listener = async_on_wake_words_changed(hass, listener)

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert listener.call_count == 1

    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, True
    )
    await hass.async_block_till_done()
    assert listener.call_count == 2

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert listener.call_count == 3

    remove_listener()
    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, False
    )
    await hass.async_block_till_done()
    assert listener.call_count == 3


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
        app_manager.return_value.async_get_addon_info = AsyncMock(
            return_value=Mock(state=AddonState.RUNNING)
        )
        setup_task = hass.async_create_task(
            hass.config_entries.async_setup(mock_config_entry.entry_id)
        )
        await info_requested.wait()
        app_manager.return_value.async_schedule_update_addon.assert_not_called()

        info.set_result(AppInfo.from_json(INFO))
        assert await setup_task

    app_manager.return_value.async_schedule_update_addon.assert_called_once_with(
        catch_error=True
    )


@pytest.mark.parametrize(
    ("wake_words", "expected_calls", "nabu_supported", "jarvis_supported"),
    [
        pytest.param(INFO["wake_words"], 0, True, False, id="unchanged"),
        pytest.param(
            [*INFO["wake_words"], {"id": "hey_jarvis", "phrase": "hey jarvis"}],
            1,
            True,
            True,
            id="model_added",
        ),
        pytest.param([], 1, False, False, id="model_removed"),
    ],
)
@pytest.mark.usefixtures("setup_integration", "preview_feature_enabled")
async def test_info_refresh_notifies_verification_changes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    wake_words: list[dict[str, str]],
    expected_calls: int,
    nabu_supported: bool,
    jarvis_supported: bool,
) -> None:
    """Test refreshes notify listeners only when verification support changes."""
    listener = Mock()
    async_on_wake_words_changed(hass, listener)
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        INFO_URL, json={**INFO, "version": "1.1.0", "wake_words": wake_words}
    )

    async_fire_time_changed(hass, dt_util.utcnow() + INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()

    assert listener.call_count == expected_calls
    assert async_verifies_wake_word(hass, "okay nabu") is nabu_supported
    assert async_verifies_wake_word(hass, "hey jarvis") is jarvis_supported


@pytest.mark.parametrize(
    ("connection_error", "send_error"),
    [
        pytest.param(aiohttp.ClientError, None, id="connection_failed"),
        pytest.param(None, aiohttp.ClientError, id="run_start_failed"),
    ],
)
@pytest.mark.usefixtures("setup_integration", "preview_feature_enabled")
async def test_run_failure_notifies_verification_loss_and_recovery(
    hass: HomeAssistant,
    connection_error: type[Exception] | None,
    send_error: type[Exception] | None,
) -> None:
    """Test listeners see lost verification and its recovery on the next refresh."""
    supported: list[bool] = []
    async_on_wake_words_changed(
        hass, lambda: supported.append(async_verifies_wake_word(hass, "okay nabu"))
    )
    websocket = Mock(send_json=AsyncMock(side_effect=send_error), close=AsyncMock())
    session = Mock(
        ws_connect=AsyncMock(return_value=websocket, side_effect=connection_error)
    )
    request = AudioRunRequest(wake_word_phrase="okay nabu", wake_word_audio_ms=500)

    with patch(
        "homeassistant.components.voice_support.client.async_get_clientsession",
        return_value=session,
    ):
        assert await async_start_run(hass, request, _no_audio()) is None
        assert supported == [False]
        assert await async_start_run(hass, request, _no_audio()) is None
        assert supported == [False]

    async_fire_time_changed(hass, dt_util.utcnow() + INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert supported == [False, True]

    async_fire_time_changed(hass, dt_util.utcnow() + 2 * INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert supported == [False, True]
