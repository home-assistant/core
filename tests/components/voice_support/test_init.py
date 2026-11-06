"""Test setting up Voice support and asking for the app."""

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
    PREVIEW_FEATURE_WAKE_WORD_VERIFICATION,
    AudioRunRequest,
    async_start_run,
)
from homeassistant.components.voice_support.client import INFO_REFRESH_INTERVAL
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


async def _no_audio() -> AsyncGenerator[bytes]:
    return
    yield


async def test_setup_entry(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test a loaded entry gives the pipeline its client, and unloading takes it."""
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
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the app is asked again now and then, and a miss is not fatal."""
    client = hass.data[DATA_CLIENT]
    assert aioclient_mock.call_count == 1

    async_fire_time_changed(hass, dt_util.utcnow() + INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2
    assert client.info is not None

    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, exc=aiohttp.ClientError)
    async_fire_time_changed(hass, dt_util.utcnow() + 2 * INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert client.info is None
    assert "nothing will be verified" not in caplog.text

    # An update to a version we do not speak is said once, not every refresh
    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=INFO)
    async_fire_time_changed(hass, dt_util.utcnow() + 3 * INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json={**INFO, "api_version": 2})
    async_fire_time_changed(hass, dt_util.utcnow() + 4 * INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + 5 * INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert client.info is None
    assert caplog.text.count("nothing will be verified") == 1
    assert setup_integration.state is ConfigEntryState.LOADED

    # Unloading stops the asking
    await hass.config_entries.async_unload(setup_integration.entry_id)
    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=INFO)
    async_fire_time_changed(hass, dt_util.utcnow() + 6 * INFO_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 0


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
            hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION, True
        )
        audio = _no_audio()
        assert await async_start_run(hass, request, audio) == "run"
        assert start_run.call_args[0] == (request, audio)


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
        hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION, feature
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
            hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION, False
        )
        await async_update_preview_feature(
            hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION, True
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
            hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION, False
        )
        await hass.async_block_till_done()
        assert create_flow.call_count == 1

        await async_update_preview_feature(
            hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION, True
        )
        await hass.async_block_till_done()
        assert create_flow.call_count == 2


async def test_a_satellite_loads_the_integration(hass: HomeAssistant) -> None:
    """Test the satellite component brings voice support with it."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "assist_satellite", {})

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
