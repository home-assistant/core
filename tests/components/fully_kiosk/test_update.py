"""Test Fully Kiosk Browser update platform."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from fullykiosk.exceptions import FullyKioskError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_fixture,
    load_json_object_fixture,
)
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from homeassistant.components.fully_kiosk.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.fully_kiosk.coordinator import (
    UPDATE_FEED_INTERVAL,
    UPDATE_FEED_RETRY_INTERVAL,
    UPDATE_FEED_URL,
)
from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_TITLE,
    ATTR_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

ENTITY_ID = "update.amazon_fire"
FILES_URL = "https://www.fully-kiosk.com/files/2026"
APK_URL = f"{FILES_URL}/10/Fully-Kiosk-Browser-v1.61.4.apk"


@pytest.fixture(autouse=True)
def device_info(
    request: pytest.FixtureRequest, mock_fully_kiosk: MagicMock
) -> dict[str, Any]:
    """Make the mocked device run an Android version that gets updates."""
    info: dict[str, Any] = {
        **load_json_object_fixture("deviceinfo.json", DOMAIN),
        "androidSdk": 30,
        **getattr(request, "param", {}),
    }
    mock_fully_kiosk.getDeviceInfo.return_value = info
    return info


@pytest.fixture(autouse=True)
def mock_poll_interval() -> Generator[None]:
    """Do not wait between polls."""
    with patch("homeassistant.components.fully_kiosk.update.POLL_INTERVAL", 0):
        yield


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> Callable[[], Awaitable[None]]:
    """Return a function to set up the integration."""

    async def setup() -> None:
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    return setup


async def install(hass: HomeAssistant, version: str | None = None) -> None:
    """Install an update."""
    data = {ATTR_ENTITY_ID: ENTITY_ID}
    if version is not None:
        data[ATTR_VERSION] = version
    await hass.services.async_call(UPDATE_DOMAIN, SERVICE_INSTALL, data, blocking=True)


@pytest.mark.parametrize(
    ("device_info", "state", "title", "latest_version", "summary", "apk"),
    [
        pytest.param(
            {},
            STATE_ON,
            "Fully Kiosk Browser",
            "1.61.4",
            "Download Fully-Kiosk-Browser-v1.61.4.apk (7.05 MB)",
            "Fully-Kiosk-Browser-v1.61.4.apk",
            id="regular",
        ),
        pytest.param(
            {"packageName": "de.ozerov.fully"},
            STATE_ON,
            "Fully Kiosk Browser",
            "1.61.4",
            "Download Fully-Kiosk-Browser-v1.61.4.apk (7.05 MB)",
            "Fully-Kiosk-Browser-v1.61.4.apk",
            id="regular_with_package",
        ),
        pytest.param(
            {"foregroundApp": "com.fullykiosk.singleapp"},
            STATE_ON,
            "Fully Kiosk Browser",
            "1.61.4",
            "Download Fully-Kiosk-Browser-v1.61.4.apk (7.05 MB)",
            "Fully-Kiosk-Browser-v1.61.4.apk",
            id="foreground_app_ignored",
        ),
        pytest.param(
            {"appVersionName": "1.61.2-emm", "packageName": "com.fullykiosk.emm"},
            STATE_ON,
            "Fully Kiosk Browser",
            "1.61.4-emm",
            "Download Fully-Kiosk-Browser-v1.61.4-emm.apk (7.61 MB)",
            "Fully-Kiosk-Browser-v1.61.4-emm.apk",
            id="emm",
        ),
        pytest.param(
            {"appVersionName": "1.20.1", "packageName": "com.fullykiosk.singleapp"},
            STATE_ON,
            "Fully Single App Kiosk",
            "1.21.4",
            "Download Fully-Single-App-Kiosk-v1.21.4.apk (7.10 MB)",
            "Fully-Single-App-Kiosk-v1.21.4.apk",
            id="single_app",
        ),
        pytest.param(
            {"appVersionName": "1.20.1", "packageName": "com.fullykiosk.videokiosk"},
            STATE_ON,
            "Fully Video Kiosk",
            "1.21.4",
            "Download Fully-Video-Kiosk-v1.21.4.apk (7.10 MB)",
            "Fully-Video-Kiosk-v1.21.4.apk",
            id="video",
        ),
    ],
    indirect=["device_info"],
)
async def test_install_latest(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fully_kiosk: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
    device_info: dict[str, Any],
    state: str,
    title: str,
    latest_version: str,
    summary: str,
    apk: str,
) -> None:
    """Test the matching release is offered and installed."""
    await setup_integration()

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry
    assert entry.unique_id == "abcdef-123456"

    entity_state = hass.states.get(ENTITY_ID)
    assert entity_state.state == state
    assert (
        entity_state.attributes[ATTR_INSTALLED_VERSION]
        == (device_info["appVersionName"])
    )
    assert entity_state.attributes[ATTR_LATEST_VERSION] == latest_version
    assert entity_state.attributes[ATTR_RELEASE_SUMMARY] == summary
    assert entity_state.attributes[ATTR_TITLE] == title
    assert entity_state.attributes[ATTR_IN_PROGRESS] is False
    assert entity_state.attributes[ATTR_SUPPORTED_FEATURES] == (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.PROGRESS
    )

    async def load_apk(url: str, force_install: bool) -> None:
        assert hass.states.get(ENTITY_ID).attributes[ATTR_IN_PROGRESS] is True
        device_info["appVersionName"] = latest_version

    mock_fully_kiosk.loadApkFile.side_effect = load_apk
    mock_fully_kiosk.getInstallApkState.return_value = {"status": "success"}

    await install(hass)

    mock_fully_kiosk.loadApkFile.assert_called_once_with(
        f"{FILES_URL}/10/{apk}", force_install=False
    )
    entity_state = hass.states.get(ENTITY_ID)
    assert entity_state.state == STATE_OFF
    assert entity_state.attributes[ATTR_INSTALLED_VERSION] == latest_version
    assert entity_state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize(
    "device_info",
    [
        pytest.param({"androidSdk": 22}, id="android_5"),
        pytest.param({"packageName": "com.fullykiosk.examkiosk"}, id="unknown_app"),
    ],
    indirect=True,
)
async def test_no_entity(
    hass: HomeAssistant, setup_integration: Callable[[], Awaitable[None]]
) -> None:
    """Test no update is offered when there is no release the device can run."""
    await setup_integration()
    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.parametrize(
    ("device_info", "version", "apk"),
    [
        pytest.param({}, "1.61.3", "Fully-Kiosk-Browser-v1.61.3.apk", id="regular"),
        pytest.param(
            {"appVersionName": "1.61.4-emm"},
            "1.61.3",
            "Fully-Kiosk-Browser-v1.61.3-emm.apk",
            id="emm",
        ),
        pytest.param(
            {"appVersionName": "1.61.4-emm"},
            "1.61.3-emm",
            "Fully-Kiosk-Browser-v1.61.3-emm.apk",
            id="emm_with_suffix",
        ),
    ],
    indirect=["device_info"],
)
async def test_install_specific_version(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
    device_info: dict[str, Any],
    version: str,
    apk: str,
) -> None:
    """Test installing a specific version."""
    await setup_integration()

    async def load_apk(url: str, force_install: bool) -> None:
        device_info["appVersionName"] = apk.removesuffix(".apk").rpartition("-v")[2]

    mock_fully_kiosk.loadApkFile.side_effect = load_apk
    mock_fully_kiosk.getInstallApkState.return_value = {"status": "success"}

    await install(hass, version)
    mock_fully_kiosk.loadApkFile.assert_called_once_with(
        f"{FILES_URL}/09/{apk}", force_install=False
    )


async def test_install_unknown_version(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
) -> None:
    """Test installing a version that is not in the feed."""
    await setup_integration()

    with pytest.raises(HomeAssistantError) as excinfo:
        await install(hass, "9.9.9")
    assert excinfo.value.translation_key == "version_not_found"
    assert excinfo.value.translation_placeholders == {"version": "9.9.9"}
    mock_fully_kiosk.loadApkFile.assert_not_called()


@pytest.mark.parametrize(
    "device_info",
    [{"appVersionName": "1.61.4"}],
    indirect=True,
)
@pytest.mark.parametrize("final_status", ["success", "idle"])
async def test_reinstall(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
    final_status: str,
) -> None:
    """Test a reinstallation is done when the device reports it."""
    await setup_integration()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    mock_fully_kiosk.getInstallApkState.side_effect = [
        {"url": APK_URL, "status": "idle"},
        {"url": APK_URL, "status": "downloading"},
        {"url": APK_URL, "status": "installing"},
        {"url": APK_URL, "status": final_status},
    ]
    await install(hass, "1.61.4")

    mock_fully_kiosk.loadApkFile.assert_called_once_with(APK_URL, force_install=True)
    assert mock_fully_kiosk.getInstallApkState.call_count == 4
    assert hass.states.get(ENTITY_ID).attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize(
    "device_info",
    [{"appVersionName": "1.54.1-play", "installerSource": "com.android.vending"}],
    indirect=True,
)
async def test_google_play_edition(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
) -> None:
    """Test the Google Play edition is informational only."""
    await setup_integration()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.54.1-play"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.61.4"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    with pytest.raises(
        HomeAssistantError, match="does not support action update.install"
    ):
        await install(hass)


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(FullyKioskError("Error", "Install failed"), id="api_error"),
        pytest.param(ClientError("Connection refused"), id="connection_error"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_install_request_error(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
    side_effect: Exception,
) -> None:
    """Test the installation cannot be requested."""
    await setup_integration()
    mock_fully_kiosk.loadApkFile.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as excinfo:
        await install(hass)
    assert excinfo.value.translation_key == "install_failed"
    assert hass.states.get(ENTITY_ID).attributes[ATTR_IN_PROGRESS] is False


async def test_install_failed(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
) -> None:
    """Test the device reports a failed installation."""
    await setup_integration()
    mock_fully_kiosk.getInstallApkState.side_effect = [
        {"url": "https://example.com/other.apk", "status": "failed"},
        {"url": APK_URL, "status": "downloading"},
        {"url": APK_URL, "status": "failed", "statustext": "Cancelled by user"},
    ]

    with pytest.raises(HomeAssistantError) as excinfo:
        await install(hass)
    assert excinfo.value.translation_key == "install_failed"
    assert mock_fully_kiosk.getInstallApkState.call_count == 3
    assert hass.states.get(ENTITY_ID).attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize("status", ["idle", "downloading", "success"])
async def test_install_timeout(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
    status: str,
) -> None:
    """Test the new version never shows up, whatever the device reports."""
    await setup_integration()
    mock_fully_kiosk.getInstallApkState.return_value = {"status": status}

    with (
        patch("homeassistant.components.fully_kiosk.update.INSTALL_TIMEOUT", 0.05),
        pytest.raises(HomeAssistantError) as excinfo,
    ):
        await install(hass)
    assert excinfo.value.translation_key == "install_timed_out"
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_install_slow_restart(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
    device_info: dict[str, Any],
) -> None:
    """Test the entity stays available until the restarted app is back."""
    await setup_integration()
    states: list[tuple[str, bool]] = []

    async def get_device_info() -> dict[str, Any]:
        state = hass.states.get(ENTITY_ID)
        states.append((state.state, state.attributes[ATTR_IN_PROGRESS]))
        if len(states) <= 8:
            raise ClientError("Connection refused")
        return {**device_info, "appVersionName": "1.61.4"}

    mock_fully_kiosk.getDeviceInfo.side_effect = get_device_info
    mock_fully_kiosk.getInstallApkState.side_effect = [
        {"status": "success"},
        *[{"status": "idle"}, ClientError("Connection refused")] * 8,
    ]

    await install(hass)

    assert states == [(STATE_ON, True)] * 9
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_device_unavailable(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entity is unavailable with the device when not installing."""
    await setup_integration()

    mock_fully_kiosk.getDeviceInfo.side_effect = ClientError
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"exc": ClientError}, id="communication_error"),
        pytest.param({"status": 500}, id="http_error"),
        pytest.param({"text": "<invalid xml"}, id="parse_error"),
    ],
)
async def test_feed_error(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    response: dict[str, Any],
) -> None:
    """Test a failed feed fetch is retried without waiting for the next poll."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(UPDATE_FEED_URL, **response)
    await setup_integration()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        UPDATE_FEED_URL, text=await async_load_fixture(hass, "feed_media.xml", DOMAIN)
    )
    freezer.tick(UPDATE_FEED_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_feed_error_keeps_releases(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test known releases stay usable when the feed cannot be refreshed."""
    await setup_integration()
    aioclient_mock.clear_requests()
    aioclient_mock.get(UPDATE_FEED_URL, exc=ClientError)

    freezer.tick(UPDATE_FEED_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == 1
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_feed_without_matching_release(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test there is no release for the app in the feed."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        UPDATE_FEED_URL, text="<rss><item><title>Empty</title></item></rss>"
    )
    await setup_integration()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_LATEST_VERSION] is None


async def test_manual_check(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the feed is fetched when checking for updates."""
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    await setup_integration()
    assert aioclient_mock.call_count == 1

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert aioclient_mock.call_count == 2


async def test_feed_reused(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the shared releases are only fetched again when stale."""
    await setup_integration()
    assert aioclient_mock.call_count == 1

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    freezer.tick(UPDATE_FEED_INTERVAL)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == 2


async def test_feed_failure_retried_on_reload(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a failed fetch is retried when the entry is set up again."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(UPDATE_FEED_URL, exc=ClientError)
    await setup_integration()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        UPDATE_FEED_URL, text=await async_load_fixture(hass, "feed_media.xml", DOMAIN)
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_feed_does_not_block_and_is_shared(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a slow feed is fetched once and does not block the setup."""
    feed = await async_load_fixture(hass, "feed_media.xml", DOMAIN)
    release = asyncio.Event()

    async def slow_response(
        method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        await release.wait()
        return AiohttpClientMockResponse(method, url, text=feed)

    aioclient_mock.clear_requests()
    aioclient_mock.get(UPDATE_FEED_URL, side_effect=slow_response)

    second_entry = MockConfigEntry(
        domain=DOMAIN, data=dict(mock_config_entry.data), unique_id="second"
    )
    for entry in (mock_config_entry, second_entry):
        entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == 1
    assert hass.states.get(ENTITY_ID).state == STATE_ON
