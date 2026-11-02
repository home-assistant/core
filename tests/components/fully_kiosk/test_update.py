"""Test Fully Kiosk Browser update platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from fullykiosk.exceptions import FullyKioskError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.fully_kiosk.const import (
    DOMAIN,
    UPDATE_FEED_URL,
    UPDATE_INTERVAL,
)
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    ATTR_TITLE,
    DATA_COMPONENT,
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

ENTITY_ID = "update.amazon_fire"


@pytest.mark.usefixtures("init_integration")
async def test_update_regular_edition(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fully_kiosk: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test standard Fully Kiosk regular edition update."""
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry
    assert entry.unique_id == "abcdef-123456"

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.42.5"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.61.4"
    assert (
        state.attributes[ATTR_RELEASE_SUMMARY]
        == "Download Fully-Kiosk-Browser-v1.61.4.apk (7.05 MB)"
    )
    assert (
        state.attributes[ATTR_RELEASE_URL]
        == "https://www.fully-kiosk.com/docs/en/getting-started/version-history"
    )
    assert state.attributes[ATTR_TITLE] == "Fully Kiosk Browser"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.PROGRESS
    )

    # Install latest update
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert len(mock_fully_kiosk.loadApkFile.mock_calls) == 1
    mock_fully_kiosk.loadApkFile.assert_called_once_with(
        "https://www.fully-kiosk.com/files/2026/10/Fully-Kiosk-Browser-v1.61.4.apk",
        force_install=False,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_IN_PROGRESS] is True

    # Simulate device updated
    device_info = await async_load_json_object_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info["appVersionName"] = "1.61.4"
    mock_fully_kiosk.getDeviceInfo.return_value = device_info

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.61.4"
    assert state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.usefixtures("init_integration")
async def test_update_specific_version(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
) -> None:
    """Test installing a specific version."""
    # Test unknown version
    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID, "version": "9.9.9"},
            blocking=True,
        )
    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "version_not_found"
    assert excinfo.value.translation_placeholders == {"version": "9.9.9"}

    # Install specific known version
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID, "version": "1.61.3"},
        blocking=True,
    )
    mock_fully_kiosk.loadApkFile.assert_called_once_with(
        "https://www.fully-kiosk.com/files/2026/09/Fully-Kiosk-Browser-v1.61.3.apk",
        force_install=False,
    )


async def test_update_up_to_date(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test when device is already up to date."""
    device_info = await async_load_json_object_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info["appVersionName"] = "1.61.4"
    mock_fully_kiosk.getDeviceInfo.return_value = device_info

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.61.4"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.61.4"

    # Force reinstall of current version
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID, "version": "1.61.4"},
        blocking=True,
    )
    mock_fully_kiosk.loadApkFile.assert_called_once_with(
        "https://www.fully-kiosk.com/files/2026/10/Fully-Kiosk-Browser-v1.61.4.apk",
        force_install=True,
    )


async def test_update_emm_edition(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device running EMM edition."""
    device_info = await async_load_json_object_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info["appVersionName"] = "1.61.2-emm"
    device_info["packageName"] = "com.fullykiosk.emm"
    mock_fully_kiosk.getDeviceInfo.return_value = device_info

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.61.2-emm"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.61.4-emm"
    assert (
        state.attributes[ATTR_RELEASE_SUMMARY]
        == "Download Fully-Kiosk-Browser-v1.61.4-emm.apk (7.61 MB)"
    )

    # Install latest update for EMM edition
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_fully_kiosk.loadApkFile.assert_called_once_with(
        "https://www.fully-kiosk.com/files/2026/10/Fully-Kiosk-Browser-v1.61.4-emm.apk",
        force_install=False,
    )


async def test_update_emm_up_to_date(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device running EMM edition that is up to date."""
    device_info = await async_load_json_object_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info["appVersionName"] = "1.61.4-emm"
    device_info["packageName"] = "com.fullykiosk.emm"
    mock_fully_kiosk.getDeviceInfo.return_value = device_info

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.61.4-emm"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.61.4-emm"


async def test_update_google_play_edition(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Google Play edition cannot be updated via APK."""
    device_info = await async_load_json_object_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info["appVersionName"] = "1.54.1-play"
    device_info["installerSource"] = "com.android.vending"
    mock_fully_kiosk.getDeviceInfo.return_value = device_info

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.54.1-play"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.61.4"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    with pytest.raises(
        HomeAssistantError, match="does not support action update.install"
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    component = hass.data[DATA_COMPONENT]
    update_entity = component.get_entity(ENTITY_ID)
    assert update_entity
    with pytest.raises(HomeAssistantError) as excinfo:
        await update_entity.async_install(version=None, backup=False)
    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "play_store_install_unsupported"


@pytest.mark.usefixtures("init_integration")
async def test_update_install_error(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
) -> None:
    """Test error when calling loadApkFile."""
    mock_fully_kiosk.loadApkFile.side_effect = FullyKioskError(
        "Error", "Install failed"
    )

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "install_failed"

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get(ATTR_IN_PROGRESS) is not True


@pytest.mark.usefixtures("mock_fully_kiosk")
async def test_update_feed_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test handling feed fetch communication error."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(UPDATE_FEED_URL, exc=ClientError)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_fully_kiosk")
async def test_update_feed_parse_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test handling feed parse error."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(UPDATE_FEED_URL, text="<invalid xml")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_update_install_timeout(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test install timing out."""
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_IN_PROGRESS] is True

    freezer.tick(timedelta(seconds=301))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_update_single_app_kiosk(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device running Fully Single App Kiosk."""
    device_info = await async_load_json_object_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info["appVersionName"] = "1.20.1"
    device_info["packageName"] = "com.fullykiosk.singleapp"
    mock_fully_kiosk.getDeviceInfo.return_value = device_info

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.20.1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.21.4"
    assert state.attributes[ATTR_TITLE] == "Fully Single App Kiosk"
    assert (
        state.attributes[ATTR_RELEASE_SUMMARY]
        == "Download Fully-Single-App-Kiosk-v1.21.4.apk (7.10 MB)"
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_fully_kiosk.loadApkFile.assert_called_once_with(
        "https://www.fully-kiosk.com/files/2026/10/Fully-Single-App-Kiosk-v1.21.4.apk",
        force_install=False,
    )


@pytest.mark.usefixtures("init_integration")
async def test_update_manual_check(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test manual update check."""
    component = hass.data[DATA_COMPONENT]
    update_entity = component.get_entity(ENTITY_ID)
    assert update_entity

    aioclient_mock.mock_calls.clear()
    await update_entity.async_update()
    assert len(aioclient_mock.mock_calls) == 1


async def test_update_polling_progress(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fully_kiosk: MagicMock,
) -> None:
    """Test progress tracking on update."""
    apk_url = (
        "https://www.fully-kiosk.com/files/2026/10/Fully-Kiosk-Browser-v1.61.4.apk"
    )
    states = [
        {"url": apk_url, "status": "downloading"},
        {"url": apk_url, "status": "installing"},
        {"url": apk_url, "status": "success"},
    ]
    mock_fully_kiosk.getInstallApkState.side_effect = states

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("homeassistant.components.fully_kiosk.update.POLL_INTERVAL", 0.01):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get(ATTR_IN_PROGRESS) is not True


async def test_update_poll_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fully_kiosk: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling install failure reported by device during polling."""
    apk_url = (
        "https://www.fully-kiosk.com/files/2026/10/Fully-Kiosk-Browser-v1.61.4.apk"
    )
    states = [
        {"url": apk_url, "status": "downloading"},
        {"url": apk_url, "status": "failed", "statustext": "Cancelled by user"},
    ]
    mock_fully_kiosk.getInstallApkState.side_effect = states

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("homeassistant.components.fully_kiosk.update.POLL_INTERVAL", 0.01):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert "failed: Cancelled by user" in caplog.text
    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get(ATTR_IN_PROGRESS) is not True


async def test_update_available_during_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fully_kiosk: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update entity remains available during app restart."""
    apk_url = (
        "https://www.fully-kiosk.com/files/2026/10/Fully-Kiosk-Browser-v1.61.4.apk"
    )
    mock_fully_kiosk.getInstallApkState.return_value = {
        "url": apk_url,
        "status": "installing",
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.state == STATE_ON

    # Simulate coordinator communication failure while Fully Kiosk restarts
    mock_fully_kiosk.getDeviceInfo.side_effect = ClientError("Connection refused")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Coordinator failed, but entity is installing so it stays available
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_IN_PROGRESS] is True


@pytest.mark.usefixtures("mock_fully_kiosk")
async def test_update_install_no_release(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test installing when no release matches."""
    empty_feed = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel></channel></rss>'
    aioclient_mock.clear_requests()
    aioclient_mock.get(UPDATE_FEED_URL, text=empty_feed)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    component = hass.data[DATA_COMPONENT]
    update_entity = component.get_entity(ENTITY_ID)
    assert update_entity

    with pytest.raises(HomeAssistantError) as excinfo:
        await update_entity.async_install(version=None, backup=False)
    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "no_release_available"


async def test_update_reinstall_polling_progress(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fully_kiosk: MagicMock,
) -> None:
    """Test progress tracking during same-version reinstall."""
    device_info = await async_load_json_object_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info["appVersionName"] = "1.61.4"
    mock_fully_kiosk.getDeviceInfo.return_value = device_info

    apk_url = (
        "https://www.fully-kiosk.com/files/2026/10/Fully-Kiosk-Browser-v1.61.4.apk"
    )
    states = [
        {"url": apk_url, "status": "downloading"},
        {"url": apk_url, "status": "installing"},
        {"url": apk_url, "status": "success"},
    ]
    mock_fully_kiosk.getInstallApkState.side_effect = states

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("homeassistant.components.fully_kiosk.update.POLL_INTERVAL", 0.01):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID, "version": "1.61.4"},
            blocking=True,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_fully_kiosk.getInstallApkState.call_count == 3
    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get(ATTR_IN_PROGRESS) is not True


async def test_update_foreground_app_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fully_kiosk: MagicMock,
) -> None:
    """Test that foregroundApp does not determine app identity."""
    device_info = await async_load_json_object_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info.pop("appPackageName", None)
    device_info.pop("packageName", None)
    device_info["foregroundApp"] = "com.fullykiosk.singleapp"
    mock_fully_kiosk.getDeviceInfo.return_value = device_info

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_TITLE] == "Fully Kiosk Browser"
