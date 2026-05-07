"""Tests for Vizio config flow."""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pyvizio.const import (
    APPS,
    DEVICE_CLASS_SPEAKER as VIZIO_DEVICE_CLASS_SPEAKER,
    DEVICE_CLASS_TV as VIZIO_DEVICE_CLASS_TV,
    INPUT_APPS,
    MAX_VOLUME,
    UNKNOWN_APP,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DOMAIN as MP_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
)
from homeassistant.components.vizio.const import (
    CONF_ADDITIONAL_CONFIGS,
    CONF_APPS,
    CONF_VOLUME_STEP,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)
from homeassistant.components.vizio.services import SERVICE_UPDATE_SETTING
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .common import (
    assert_key_press,
    assert_launch_app,
    assert_no_launch_app,
    assert_set_input,
    assert_set_setting,
    override_audio_options,
    override_audio_settings,
    override_current_app,
    override_power,
    override_unavailable,
    setup_integration,
)
from .const import (
    ADDITIONAL_APP_CONFIG,
    APP_LIST,
    APP_NAME_LIST,
    CURRENT_APP,
    CURRENT_EQ,
    CURRENT_INPUT,
    CUSTOM_CONFIG,
    ENTITY_ID,
    EQ_LIST,
    HOST,
    INPUT_LIST,
    INPUT_LIST_WITH_APPS,
    MOCK_TV_WITH_ADDITIONAL_APPS_CONFIG,
    MOCK_TV_WITH_EXCLUDE_CONFIG,
    MOCK_TV_WITH_INCLUDE_CONFIG,
    NAME,
    UNIQUE_ID,
    UNKNOWN_APP_CONFIG,
    VOLUME_STEP,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def media_player_only() -> Generator[None]:
    """Only set up the media_player platform."""
    with patch("homeassistant.components.vizio.PLATFORMS", [Platform.MEDIA_PLAYER]):
        yield


@pytest.mark.parametrize(
    "mock_config_entry_fixture",
    ["mock_tv_config_entry", "mock_speaker_config_entry"],
    ids=["tv", "speaker"],
)
@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_media_player_entity_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test media player entity is created for TV and speaker."""
    config_entry: MockConfigEntry = request.getfixturevalue(mock_config_entry_fixture)
    await setup_integration(hass, config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


def _assert_sources_and_volume(attr: dict[str, Any], vizio_device_class: str) -> None:
    """Assert source list, source, and volume level based on attr dict and device class."""
    assert attr[ATTR_INPUT_SOURCE_LIST] == INPUT_LIST
    assert attr[ATTR_INPUT_SOURCE] == CURRENT_INPUT
    assert (
        attr["volume_level"]
        == float(int(MAX_VOLUME[vizio_device_class] / 2))
        / MAX_VOLUME[vizio_device_class]
    )


def _get_attr_and_assert_base_attr(
    hass: HomeAssistant, device_class: str, power_state: str
) -> dict[str, Any]:
    """Return entity attributes after asserting name, device class, and power state."""
    attr = hass.states.get(ENTITY_ID).attributes
    assert attr["friendly_name"] == NAME
    assert attr["device_class"] == device_class
    assert hass.states.get(ENTITY_ID).state == power_state
    return attr


async def _setup_tv_on(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up a TV that's powered on and verify base/source/volume/sound-mode."""
    await setup_integration(hass, config_entry)
    attr = _get_attr_and_assert_base_attr(hass, MediaPlayerDeviceClass.TV, STATE_ON)
    _assert_sources_and_volume(attr, VIZIO_DEVICE_CLASS_TV)
    assert attr[ATTR_SOUND_MODE] == CURRENT_EQ


async def _setup_tv_off(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Set up a TV that's powered off."""
    with override_power(aioclient_mock, HOST, "tv", "power_off"):
        await setup_integration(hass, config_entry)
    _get_attr_and_assert_base_attr(hass, MediaPlayerDeviceClass.TV, STATE_OFF)


async def _setup_speaker_on(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up a speaker that's powered on and verify base/source/volume/sound-mode."""
    await setup_integration(hass, config_entry)
    attr = _get_attr_and_assert_base_attr(
        hass, MediaPlayerDeviceClass.SPEAKER, STATE_ON
    )
    _assert_sources_and_volume(attr, VIZIO_DEVICE_CLASS_SPEAKER)
    assert "sound_mode" in attr


async def _setup_speaker_off(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Set up a speaker that's powered off."""
    with override_power(aioclient_mock, HOST, "speaker", "power_off"):
        await setup_integration(hass, config_entry)
    _get_attr_and_assert_base_attr(hass, MediaPlayerDeviceClass.SPEAKER, STATE_OFF)


@asynccontextmanager
async def _setup_tv_with_app(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    current_app_fixture: str,
) -> AsyncIterator[None]:
    """Set up a TV with apps support and a specific running-app fixture."""
    with (
        override_audio_settings(aioclient_mock, HOST, "tv", "audio_settings_no_eq"),
        override_current_app(aioclient_mock, HOST, current_app_fixture),
    ):
        await setup_integration(hass, config_entry)
        attr = _get_attr_and_assert_base_attr(hass, MediaPlayerDeviceClass.TV, STATE_ON)
        assert (
            attr["volume_level"]
            == float(int(MAX_VOLUME[VIZIO_DEVICE_CLASS_TV] / 2))
            / MAX_VOLUME[VIZIO_DEVICE_CLASS_TV]
        )
        yield


def _assert_source_list_with_apps(
    list_to_test: list[str], attr: dict[str, Any]
) -> None:
    """Assert source list matches list_to_test after removing INPUT_APPS from list."""
    for app_to_remove in INPUT_APPS:
        if app_to_remove in list_to_test:
            list_to_test.remove(app_to_remove)

    assert attr[ATTR_INPUT_SOURCE_LIST] == list_to_test


async def _call_service(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    domain: str,
    service: str,
    extra_data: dict[str, Any] | None = None,
) -> None:
    """Clear prior HTTP calls and invoke ``service`` on the entity."""
    aioclient_mock.mock_calls.clear()
    service_data = {ATTR_ENTITY_ID: ENTITY_ID}
    if extra_data:
        service_data.update(extra_data)
    await hass.services.async_call(domain, service, service_data, blocking=True)


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_speaker_on(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_speaker_config_entry: MockConfigEntry,
) -> None:
    """Test Vizio Speaker entity setup when on."""
    await _setup_speaker_on(hass, mock_speaker_config_entry)


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_speaker_off(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_speaker_config_entry: MockConfigEntry,
) -> None:
    """Test Vizio Speaker entity setup when off."""
    await _setup_speaker_off(hass, aioclient_mock, mock_speaker_config_entry)


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_init_tv_on(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_tv_config_entry: MockConfigEntry,
) -> None:
    """Test Vizio TV entity setup when on."""
    await _setup_tv_on(hass, mock_tv_config_entry)


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_init_tv_off(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_tv_config_entry: MockConfigEntry,
) -> None:
    """Test Vizio TV entity setup when off."""
    await _setup_tv_off(hass, aioclient_mock, mock_tv_config_entry)


@pytest.mark.usefixtures("vizio_cant_connect")
async def test_setup_unavailable_speaker(
    hass: HomeAssistant, mock_speaker_config_entry: MockConfigEntry
) -> None:
    """Test speaker config entry retries setup when device is unavailable."""
    mock_speaker_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_speaker_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_speaker_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("vizio_cant_connect")
async def test_setup_unavailable_tv(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test TV config entry retries setup when device is unavailable."""
    mock_tv_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_tv_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_tv_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_services(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_tv_config_entry: MockConfigEntry,
) -> None:
    """Test all Vizio media player entity services."""
    await _setup_tv_on(hass, mock_tv_config_entry)

    await _call_service(aioclient_mock, hass, MP_DOMAIN, SERVICE_TURN_ON)
    assert_key_press(aioclient_mock, "tv", "POW_ON")

    await _call_service(aioclient_mock, hass, MP_DOMAIN, SERVICE_TURN_OFF)
    assert_key_press(aioclient_mock, "tv", "POW_OFF")

    await _call_service(
        aioclient_mock,
        hass,
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: True},
    )
    assert_key_press(aioclient_mock, "tv", "MUTE_ON")

    await _call_service(
        aioclient_mock,
        hass,
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: False},
    )
    assert_key_press(aioclient_mock, "tv", "MUTE_OFF")

    await _call_service(
        aioclient_mock,
        hass,
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: "HDMI-2"},
    )
    assert_set_input(aioclient_mock, "HDMI-2")

    await _call_service(aioclient_mock, hass, MP_DOMAIN, SERVICE_VOLUME_UP)
    assert_key_press(aioclient_mock, "tv", "VOL_UP", count=DEFAULT_VOLUME_STEP)

    await _call_service(aioclient_mock, hass, MP_DOMAIN, SERVICE_VOLUME_DOWN)
    assert_key_press(aioclient_mock, "tv", "VOL_DOWN", count=DEFAULT_VOLUME_STEP)

    # SERVICE_VOLUME_SET 1.0 from current 50/100 → 50 VOL_UP presses.
    await _call_service(
        aioclient_mock,
        hass,
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_MEDIA_VOLUME_LEVEL: 1},
    )
    assert_key_press(aioclient_mock, "tv", "VOL_UP", count=50)

    # After the previous set, optimistic volume is 100/100; setting to 0
    # requires 100 VOL_DOWN presses.
    await _call_service(
        aioclient_mock,
        hass,
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_MEDIA_VOLUME_LEVEL: 0},
    )
    assert_key_press(aioclient_mock, "tv", "VOL_DOWN", count=100)

    await _call_service(aioclient_mock, hass, MP_DOMAIN, SERVICE_MEDIA_NEXT_TRACK)
    assert_key_press(aioclient_mock, "tv", "CH_UP")

    await _call_service(aioclient_mock, hass, MP_DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK)
    assert_key_press(aioclient_mock, "tv", "CH_DOWN")

    await _call_service(
        aioclient_mock,
        hass,
        MP_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_SOUND_MODE: "Music"},
    )
    assert_set_setting(aioclient_mock, name="eq", value="Music")

    # SERVICE_UPDATE_SETTING normalizes name+value via the config-flow schema.
    await _call_service(
        aioclient_mock,
        hass,
        DOMAIN,
        SERVICE_UPDATE_SETTING,
        {"setting_type": "Audio", "setting_name": "AV Delay", "new_value": "0"},
    )
    assert_set_setting(aioclient_mock, name="av_delay", value=0)

    await _call_service(
        aioclient_mock,
        hass,
        DOMAIN,
        SERVICE_UPDATE_SETTING,
        {"setting_type": "Audio", "setting_name": "EQ", "new_value": "Music"},
    )
    assert_set_setting(aioclient_mock, name="eq", value="Music")

    await _call_service(aioclient_mock, hass, MP_DOMAIN, SERVICE_MEDIA_PLAY)
    assert_key_press(aioclient_mock, "tv", "PLAY")

    await _call_service(aioclient_mock, hass, MP_DOMAIN, SERVICE_MEDIA_PAUSE)
    assert_key_press(aioclient_mock, "tv", "PAUSE")


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_options_update(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_speaker_config_entry: MockConfigEntry,
) -> None:
    """Test when config entry update event fires."""
    await _setup_speaker_on(hass, mock_speaker_config_entry)
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.options
    new_options = config_entry.options.copy()
    updated_options = {CONF_VOLUME_STEP: VOLUME_STEP}
    new_options.update(updated_options)
    hass.config_entries.async_update_entry(
        entry=config_entry,
        options=new_options,
    )
    assert config_entry.options == updated_options
    await hass.async_block_till_done()
    await _call_service(aioclient_mock, hass, MP_DOMAIN, SERVICE_VOLUME_UP)
    assert_key_press(aioclient_mock, "speaker", "VOL_UP", count=VOLUME_STEP)


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_update_available_to_unavailable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_speaker_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device becomes unavailable after being available."""
    await _setup_speaker_on(hass, mock_speaker_config_entry)

    # Simulate device becoming unreachable.
    with override_unavailable(aioclient_mock, HOST, "speaker"):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_update_unavailable_to_available(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_speaker_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device becomes available after being unavailable."""
    await _setup_speaker_on(hass, mock_speaker_config_entry)

    # First, make device unavailable.
    with override_unavailable(aioclient_mock, HOST, "speaker"):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # Then make device available again — base ``vizio_update`` mocks remain
    # registered so removing the override is enough.
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("vizio_connect", "vizio_update_with_apps")
async def test_setup_with_apps(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_tv_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device setup with apps."""
    # vizio_update_with_apps already serves the Hulu running-app fixture,
    # so the helper just overrides audio_settings to the no-eq variant.
    async with _setup_tv_with_app(
        hass, aioclient_mock, mock_tv_config_entry, "current_app_hulu"
    ):
        attr = hass.states.get(ENTITY_ID).attributes
        _assert_source_list_with_apps(list(INPUT_LIST_WITH_APPS + APP_NAME_LIST), attr)
        assert CURRENT_APP in attr[ATTR_INPUT_SOURCE_LIST]
        assert attr[ATTR_INPUT_SOURCE] == CURRENT_APP
        assert attr["app_name"] == CURRENT_APP
        assert "app_id" not in attr

    # Selecting "Hulu" should fire a launch_app PUT with Hulu's app config.
    hulu = next(c for app in APP_LIST if app["name"] == "Hulu" for c in app["config"])
    await _call_service(
        aioclient_mock,
        hass,
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: CURRENT_APP},
    )
    assert_launch_app(
        aioclient_mock,
        app_id=hulu["APP_ID"],
        name_space=hulu["NAME_SPACE"],
        message=hulu.get("MESSAGE"),
    )


@pytest.mark.usefixtures("vizio_connect", "vizio_update_with_apps")
async def test_setup_with_apps_include(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device setup with apps and apps["include"] in config."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_TV_WITH_INCLUDE_CONFIG, unique_id=UNIQUE_ID
    )
    async with _setup_tv_with_app(
        hass, aioclient_mock, config_entry, "current_app_hulu"
    ):
        attr = hass.states.get(ENTITY_ID).attributes
        _assert_source_list_with_apps([*INPUT_LIST_WITH_APPS, CURRENT_APP], attr)
        assert CURRENT_APP in attr[ATTR_INPUT_SOURCE_LIST]
        assert attr[ATTR_INPUT_SOURCE] == CURRENT_APP
        assert attr["app_name"] == CURRENT_APP
        assert "app_id" not in attr


@pytest.mark.usefixtures("vizio_connect", "vizio_update_with_apps")
async def test_setup_with_apps_exclude(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device setup with apps and apps["exclude"] in config."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_TV_WITH_EXCLUDE_CONFIG, unique_id=UNIQUE_ID
    )
    async with _setup_tv_with_app(
        hass, aioclient_mock, config_entry, "current_app_hulu"
    ):
        attr = hass.states.get(ENTITY_ID).attributes
        _assert_source_list_with_apps([*INPUT_LIST_WITH_APPS, CURRENT_APP], attr)
        assert CURRENT_APP in attr[ATTR_INPUT_SOURCE_LIST]
        assert attr[ATTR_INPUT_SOURCE] == CURRENT_APP
        assert attr["app_name"] == CURRENT_APP
        assert "app_id" not in attr


@pytest.mark.usefixtures("vizio_connect", "vizio_update_with_apps")
async def test_setup_with_apps_additional_apps_config(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device setup with apps and apps["additional_configs"] in config."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_TV_WITH_ADDITIONAL_APPS_CONFIG, unique_id=UNIQUE_ID
    )
    # current_app_custom.json holds APP_ID="test", NAME_SPACE=10 — the
    # custom config the test's additional_configs entry maps to "Hulu".
    async with _setup_tv_with_app(
        hass, aioclient_mock, config_entry, "current_app_custom"
    ):
        attr = hass.states.get(ENTITY_ID).attributes
        assert attr[ATTR_INPUT_SOURCE_LIST].count(CURRENT_APP) == 1
        _assert_source_list_with_apps(
            list(
                INPUT_LIST_WITH_APPS
                + APP_NAME_LIST
                + [
                    app["name"]
                    for app in MOCK_TV_WITH_ADDITIONAL_APPS_CONFIG[CONF_APPS][
                        CONF_ADDITIONAL_CONFIGS
                    ]
                    if app["name"] not in APP_NAME_LIST
                ]
            ),
            attr,
        )
        assert ADDITIONAL_APP_CONFIG["name"] in attr[ATTR_INPUT_SOURCE_LIST]
        assert attr[ATTR_INPUT_SOURCE] == ADDITIONAL_APP_CONFIG["name"]
        assert attr["app_name"] == ADDITIONAL_APP_CONFIG["name"]
        assert "app_id" not in attr

    # Selecting "Netflix" launches it with its catalog config.
    netflix = next(
        c for app in APP_LIST if app["name"] == "Netflix" for c in app["config"]
    )
    await _call_service(
        aioclient_mock,
        hass,
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: "Netflix"},
    )
    assert_launch_app(
        aioclient_mock,
        app_id=netflix["APP_ID"],
        name_space=netflix["NAME_SPACE"],
        message=netflix.get("MESSAGE"),
    )

    # Selecting CURRENT_APP ("Hulu") with the additional config in place
    # launches it via launch_app_config (custom config from CUSTOM_CONFIG).
    await _call_service(
        aioclient_mock,
        hass,
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: CURRENT_APP},
    )
    assert_launch_app(
        aioclient_mock,
        app_id=CUSTOM_CONFIG["APP_ID"],
        name_space=CUSTOM_CONFIG["NAME_SPACE"],
        message=CUSTOM_CONFIG.get("MESSAGE"),
    )

    # Selecting an unknown source should not result in any /app/launch PUT.
    aioclient_mock.mock_calls.clear()
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "_"},
        blocking=True,
    )
    assert_no_launch_app(aioclient_mock)


@pytest.mark.usefixtures("vizio_connect", "vizio_update_with_apps")
async def test_setup_with_unknown_app_config(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_tv_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device setup with apps where app config returned is unknown."""
    async with _setup_tv_with_app(
        hass, aioclient_mock, mock_tv_config_entry, "current_app_unknown"
    ):
        attr = hass.states.get(ENTITY_ID).attributes
        _assert_source_list_with_apps(list(INPUT_LIST_WITH_APPS + APP_NAME_LIST), attr)
        assert attr[ATTR_INPUT_SOURCE] == UNKNOWN_APP
        assert attr["app_name"] == UNKNOWN_APP
        assert attr["app_id"] == UNKNOWN_APP_CONFIG


@pytest.mark.usefixtures("vizio_connect", "vizio_update_with_apps")
async def test_setup_with_no_running_app(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_tv_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device setup with apps where no app is running."""
    async with _setup_tv_with_app(
        hass, aioclient_mock, mock_tv_config_entry, "current_app_none"
    ):
        attr = hass.states.get(ENTITY_ID).attributes
        _assert_source_list_with_apps(list(INPUT_LIST_WITH_APPS + APP_NAME_LIST), attr)
        assert attr[ATTR_INPUT_SOURCE] == "CAST"
        assert "app_id" not in attr
        assert "app_name" not in attr


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_setup_tv_without_mute(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_tv_config_entry: MockConfigEntry,
) -> None:
    """Test Vizio TV entity setup when mute property isn't returned by Vizio API."""
    with override_audio_settings(
        aioclient_mock, HOST, "tv", "audio_settings_volume_only"
    ):
        await setup_integration(hass, mock_tv_config_entry)
    attr = _get_attr_and_assert_base_attr(hass, MediaPlayerDeviceClass.TV, STATE_ON)
    _assert_sources_and_volume(attr, VIZIO_DEVICE_CLASS_TV)
    assert "sound_mode" not in attr
    assert "is_volume_muted" not in attr


@pytest.mark.usefixtures("vizio_connect", "vizio_update_with_apps")
async def test_apps_update(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_tv_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device setup with apps where no app is running."""
    with patch(
        "homeassistant.components.vizio.coordinator.gen_apps_list_from_url",
        return_value=None,
    ):
        async with _setup_tv_with_app(
            hass, aioclient_mock, mock_tv_config_entry, "current_app_none"
        ):
            # Check source list, remove TV inputs, and verify that the integration is
            # using the default APPS list
            sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
            apps = list(set(sources) - set(INPUT_LIST))
            assert len(apps) == len(APPS)

            with patch(
                "homeassistant.components.vizio.coordinator.gen_apps_list_from_url",
                return_value=APP_LIST,
            ):
                async_fire_time_changed(hass, dt_util.now() + timedelta(days=2))
                await hass.async_block_till_done()
                async_fire_time_changed(hass, dt_util.now() + timedelta(days=2))
                await hass.async_block_till_done()
                # Check source list, remove TV inputs, and verify that the integration is
                # now using the APP_LIST list
                sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
                apps = list(set(sources) - set(INPUT_LIST))
                assert len(apps) == len(APP_LIST)


@pytest.mark.usefixtures("vizio_connect", "vizio_update_with_apps_on_input")
async def test_vizio_update_with_apps_on_input(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test a vizio TV with apps that is on a TV input."""
    await setup_integration(hass, mock_tv_config_entry)
    attr = _get_attr_and_assert_base_attr(hass, MediaPlayerDeviceClass.TV, STATE_ON)
    # app ID should not be in the attributes
    assert "app_id" not in attr


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_coordinator_update_on_to_off(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_speaker_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device transitions from on to off during coordinator refresh."""
    await _setup_speaker_on(hass, mock_speaker_config_entry)
    attr = _get_attr_and_assert_base_attr(
        hass, MediaPlayerDeviceClass.SPEAKER, STATE_ON
    )
    assert attr[ATTR_MEDIA_VOLUME_LEVEL] is not None
    assert ATTR_SOUND_MODE in attr

    # Device turns off.
    with override_power(aioclient_mock, HOST, "speaker", "power_off"):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert hass.states.get(ENTITY_ID).state == STATE_OFF
        attr = hass.states.get(ENTITY_ID).attributes
        assert attr.get(ATTR_MEDIA_VOLUME_LEVEL) is None
        assert attr.get(ATTR_MEDIA_VOLUME_MUTED) is None
        assert attr.get(ATTR_SOUND_MODE) is None


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_coordinator_update_off_to_on(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_speaker_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device transitions from off to on during coordinator refresh."""
    await _setup_speaker_off(hass, aioclient_mock, mock_speaker_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    # Device turns on
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    attr = hass.states.get(ENTITY_ID).attributes
    assert attr[ATTR_MEDIA_VOLUME_LEVEL] is not None
    assert ATTR_SOUND_MODE in attr


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_sound_mode_feature_toggling(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_speaker_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sound mode feature is added when present and removed when absent."""
    await _setup_speaker_on(hass, mock_speaker_config_entry)
    attr = _get_attr_and_assert_base_attr(
        hass, MediaPlayerDeviceClass.SPEAKER, STATE_ON
    )
    assert ATTR_SOUND_MODE in attr
    state = hass.states.get(ENTITY_ID)
    assert (
        state.attributes["supported_features"]
        & MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )

    # Override to a state with no eq item; integration should drop the
    # SELECT_SOUND_MODE feature.
    with override_audio_settings(
        aioclient_mock, HOST, "speaker", "audio_settings_no_eq"
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON
        assert not (
            state.attributes["supported_features"]
            & MediaPlayerEntityFeature.SELECT_SOUND_MODE
        )


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_sound_mode_list_cached(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_speaker_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sound mode list is cached after first retrieval."""
    await _setup_speaker_on(hass, mock_speaker_config_entry)
    attr = hass.states.get(ENTITY_ID).attributes
    assert attr["sound_mode_list"] == EQ_LIST

    # Override the audio-options endpoint with a different EQ list — the
    # cached value should persist regardless.
    with override_audio_options(aioclient_mock, HOST, "speaker", "audio_options_alt"):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        attr = hass.states.get(ENTITY_ID).attributes
        # Sound mode list should still be the original cached list.
        assert attr["sound_mode_list"] == EQ_LIST
