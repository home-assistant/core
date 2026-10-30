"""The tests for the Template media player platform."""

from enum import StrEnum
from http import HTTPStatus
from itertools import chain
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_mock_restore_state_shutdown_restart,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import media_player, template
from homeassistant.components.media_player import (
    MediaPlayerEntityCapabilityAttribute,
    MediaPlayerEntityFeature,
    MediaPlayerEntityStateAttribute,
    MediaPlayerState,
)
from homeassistant.components.template.media_player import (
    DEFAULT_NAME,
    RESTORED_MEDIA_TEMPLATES,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    assert_attributes_template,
    assert_extra_template_attributes,
    assert_invalid_config_entry_actions_do_not_create_entities,
    assert_invalid_yaml_actions_do_not_create_entities,
    assert_state_and_attributes,
    async_get_flow_preview_state,
    async_trigger,
    make_test_action,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
    setup_mock_template_entity_restore_state,
    setup_restore_template_entity,
)

TEST_STATE_ENTITY_ID = "sensor.test_state"
TEST_AVAILABILITY_ENTITY_ID = "binary_sensor.availability"
TEST_MEDIA_PLAYER = TemplatePlatformSetup(
    media_player.DOMAIN,
    "test_template_media_player",
    make_test_trigger(TEST_STATE_ENTITY_ID, TEST_AVAILABILITY_ENTITY_ID),
)

STATE_TEMPLATE = "{{ states('sensor.test_state') }}"
SOURCE_LIST = {"source_list": "{{ ['TV', 'Radio'] }}"}
SOUND_MODE_LIST = {"sound_mode_list": "{{ ['Movie', 'Music'] }}"}

ON_OFF_ACTIONS = {
    **make_test_action("turn_on"),
    **make_test_action("turn_off"),
}
NO_MEDIA_DATA = {
    "media": {option: None for option, _ in RESTORED_MEDIA_TEMPLATES},
    "media_position_updated_at": None,
}
PLAYBACK_ACTIONS = {
    **make_test_action("media_play"),
    **make_test_action("media_pause"),
    **make_test_action("media_stop"),
}


def _attribute_template(attribute: str) -> str:
    return f"{{{{ state_attr('{TEST_STATE_ENTITY_ID}', '{attribute}') }}}}"


async def _async_call_media_player(hass: HomeAssistant, service: str) -> None:
    await hass.services.async_call(
        media_player.DOMAIN,
        service,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id},
        blocking=True,
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("rendered", "expected"),
    [
        pytest.param("playing", MediaPlayerState.PLAYING, id="playing"),
        pytest.param("paused", MediaPlayerState.PAUSED, id="paused"),
        pytest.param("idle", MediaPlayerState.IDLE, id="idle"),
        pytest.param("on", MediaPlayerState.ON, id="on"),
        pytest.param("off", MediaPlayerState.OFF, id="off"),
        pytest.param("true", MediaPlayerState.ON, id="boolean_true"),
        pytest.param("false", MediaPlayerState.OFF, id="boolean_false"),
        pytest.param("standby", STATE_UNKNOWN, id="deprecated_standby"),
        pytest.param("buffering", MediaPlayerState.BUFFERING, id="buffering"),
        pytest.param("nonsense", STATE_UNKNOWN, id="invalid"),
    ],
)
async def test_state_template(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    rendered: str,
    expected: str,
) -> None:
    """Test the state template."""
    await setup_entity(hass, TEST_MEDIA_PLAYER, style, 1, {}, STATE_TEMPLATE)
    await async_trigger(hass, TEST_STATE_ENTITY_ID, rendered)
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, expected)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_deprecated_standby_state_logs_error(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the deprecated standby state is rejected with an error."""
    await setup_entity(hass, TEST_MEDIA_PLAYER, style, 1, {}, STATE_TEMPLATE)
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "standby")
    assert "Received invalid media_player state: standby" in caplog.text


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("option", "extra_config", "value", "expected"),
    [
        pytest.param("app_id", {}, "com.app", "com.app", id="app_id"),
        pytest.param("app_name", {}, "App", "App", id="app_name"),
        pytest.param("media_album_artist", {}, "A", "A", id="media_album_artist"),
        pytest.param("media_album_name", {}, "B", "B", id="media_album_name"),
        pytest.param("media_artist", {}, "C", "C", id="media_artist"),
        pytest.param("media_channel", {}, "D", "D", id="media_channel"),
        pytest.param("media_content_id", {}, 1234, "1234", id="media_content_id"),
        pytest.param("media_content_type", {}, "music", "music", id="content_type"),
        pytest.param("media_episode", {}, "E", "E", id="media_episode"),
        pytest.param("media_playlist", {}, "F", "F", id="media_playlist"),
        pytest.param("media_season", {}, "G", "G", id="media_season"),
        pytest.param("media_series_title", {}, "H", "H", id="media_series_title"),
        pytest.param("media_title", {}, "I", "I", id="media_title"),
        pytest.param("media_duration", {}, 300, 300, id="media_duration"),
        pytest.param("media_track", {}, 3, 3, id="media_track"),
        pytest.param("volume_level", {}, 0.5, 0.5, id="volume_level"),
        pytest.param("volume_level", {}, 1.5, None, id="volume_level_too_high"),
        pytest.param("volume_level", {}, -0.1, None, id="volume_level_too_low"),
        pytest.param("volume_level", {}, "loud", None, id="volume_level_invalid"),
        pytest.param("media_duration", {}, -1, None, id="media_duration_negative"),
        pytest.param("media_duration", {}, "long", None, id="media_duration_invalid"),
        pytest.param("media_position", {}, -1, None, id="media_position_negative"),
        pytest.param("media_position", {}, "half", None, id="media_position_invalid"),
        pytest.param("media_track", {}, -1, None, id="media_track_negative"),
        pytest.param("media_track", {}, "first", None, id="media_track_invalid"),
        pytest.param("is_volume_muted", {}, True, True, id="is_volume_muted"),
        pytest.param("is_volume_muted", {}, "maybe", None, id="muted_invalid"),
        pytest.param("shuffle", {}, False, False, id="shuffle"),
        pytest.param("shuffle", {}, "maybe", None, id="shuffle_invalid"),
        pytest.param("repeat", {}, "one", "one", id="repeat"),
        pytest.param("repeat", {}, "never", None, id="repeat_invalid"),
        pytest.param("source", SOURCE_LIST, "TV", "TV", id="source"),
        pytest.param("source", SOURCE_LIST, "DVD", None, id="source_not_in_list"),
        pytest.param("sound_mode", SOUND_MODE_LIST, "Movie", "Movie", id="sound_mode"),
        pytest.param(
            "sound_mode", SOUND_MODE_LIST, "Disco", None, id="sound_mode_not_in_list"
        ),
    ],
)
async def test_attribute_templates(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    option: str,
    extra_config: ConfigType,
    value: Any,
    expected: Any,
) -> None:
    """Test attribute templates."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {option: _attribute_template(option), **extra_config},
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing", {option: value})
    state = hass.states.get(TEST_MEDIA_PLAYER.entity_id)
    assert state.attributes.get(option) == expected


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize("option", ["media_title", "volume_level"])
async def test_attribute_template_error(
    hass: HomeAssistant, style: ConfigurationStyle, option: str
) -> None:
    """Test an attribute template error clears the attribute only."""
    await setup_entity(
        hass, TEST_MEDIA_PLAYER, style, 1, {option: "{{ x - 1 }}"}, STATE_TEMPLATE
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing")
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, "playing", {option: None})


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("option", "action", "values"),
    [
        pytest.param("source_list", "select_source", ["TV", "Radio"], id="source_list"),
        pytest.param(
            "sound_mode_list",
            "select_sound_mode",
            ["Movie", "Music"],
            id="sound_mode_list",
        ),
    ],
)
async def test_list_templates(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    option: str,
    action: str,
    values: list[str],
) -> None:
    """Test list templates are exposed with their select action."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {option: _attribute_template(option), **make_test_action(action)},
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "on", {option: values})
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, "on", {option: values})


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_media_position_updated_at(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the position timestamp only moves when the position changes."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {"media_position": _attribute_template("media_position")},
        STATE_TEMPLATE,
    )
    first_update = dt_util.utcnow()
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing", {"media_position": 10})
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        {"media_position": 10, "media_position_updated_at": first_update},
    )

    freezer.tick(5)
    await async_trigger(
        hass, TEST_STATE_ENTITY_ID, "playing", {"media_position": 10, "other": 1}
    )
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        {"media_position": 10, "media_position_updated_at": first_update},
    )

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing", {"media_position": 15})
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        {"media_position": 15, "media_position_updated_at": dt_util.utcnow()},
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_media_position_updated_at_state_change(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the position timestamp is rebased when resuming at the same position."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {"media_position": _attribute_template("media_position")},
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "paused", {"media_position": 30})

    freezer.tick(300)
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing", {"media_position": 30})
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        {"media_position": 30, "media_position_updated_at": dt_util.utcnow()},
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_media_position_reset_on_media_change(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a new media item at an unchanged position restarts the position clock."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {
            "media_content_id": _attribute_template("media_content_id"),
            "media_position": _attribute_template("media_position"),
        },
        STATE_TEMPLATE,
    )
    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "playing",
        {"media_content_id": "track_1", "media_position": 0},
    )

    freezer.tick(120)
    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "playing",
        {"media_content_id": "track_2", "media_position": 0},
    )
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        {
            "media_content_id": "track_2",
            "media_position": 0,
            "media_position_updated_at": dt_util.utcnow(),
        },
    )


@pytest.mark.usefixtures("calls")
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_media_position_updated_at_optimistic_play(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the play action rebases the position timestamp."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {
            **PLAYBACK_ACTIONS,
            "media_position": _attribute_template("media_position"),
        },
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "on", {"media_position": 30})
    await hass.services.async_call(
        media_player.DOMAIN,
        "media_pause",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id},
        blocking=True,
    )

    freezer.tick(300)
    await hass.services.async_call(
        media_player.DOMAIN,
        "media_play",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id},
        blocking=True,
    )
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        {"media_position": 30, "media_position_updated_at": dt_util.utcnow()},
    )


@pytest.mark.usefixtures("calls")
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("elapsed", "attributes", "expected_position"),
    [
        pytest.param(20, {}, 50, id="elapsed"),
        pytest.param(400, {"media_duration": 300}, 300, id="capped_at_duration"),
    ],
)
async def test_media_position_optimistic_play_pause_play(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    freezer: FrozenDateTimeFactory,
    elapsed: int,
    attributes: dict[str, Any],
    expected_position: int,
) -> None:
    """Test pausing keeps the playback elapsed since the last position sample."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {
            **PLAYBACK_ACTIONS,
            "media_duration": _attribute_template("media_duration"),
            "media_position": _attribute_template("media_position"),
        },
    )
    await async_trigger(
        hass, TEST_STATE_ENTITY_ID, "on", {"media_position": 30, **attributes}
    )

    await _async_call_media_player(hass, "media_play")

    freezer.tick(elapsed)
    await _async_call_media_player(hass, "media_pause")
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "paused",
        {
            "media_position": expected_position,
            "media_position_updated_at": dt_util.utcnow(),
        },
    )

    # The pause must not count towards the resumed position.
    freezer.tick(60)
    await _async_call_media_player(hass, "media_play")
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        {
            "media_position": expected_position,
            "media_position_updated_at": dt_util.utcnow(),
        },
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "sampled_position",
    [
        pytest.param(50, id="fresh_sample"),
        pytest.param(30, id="unchanged_sample"),
    ],
)
async def test_media_position_sample_on_pause(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    freezer: FrozenDateTimeFactory,
    sampled_position: int,
) -> None:
    """Test pausing keeps the elapsed playback whether or not a new sample arrives."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {"media_position": _attribute_template("media_position")},
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing", {"media_position": 30})

    freezer.tick(20)
    await async_trigger(
        hass, TEST_STATE_ENTITY_ID, "paused", {"media_position": sampled_position}
    )
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "paused",
        {"media_position": 50, "media_position_updated_at": dt_util.utcnow()},
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_entity_picture(hass: HomeAssistant, style: ConfigurationStyle) -> None:
    """Test the media image is proxied and the picture is used as a fallback."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {
            "picture": "/local/tv.png",
            "media_image_url": _attribute_template("media_image_url"),
        },
        STATE_TEMPLATE,
    )
    await async_trigger(
        hass, TEST_STATE_ENTITY_ID, "playing", {"media_image_url": "/local/art.png"}
    )
    state = hass.states.get(TEST_MEDIA_PLAYER.entity_id)
    assert state.attributes[ATTR_ENTITY_PICTURE].startswith(
        f"/api/media_player_proxy/{TEST_MEDIA_PLAYER.entity_id}?token="
    )

    await async_trigger(
        hass, TEST_STATE_ENTITY_ID, "off", {"media_image_url": "/local/art.png"}
    )
    assert_state_and_attributes(
        hass, TEST_MEDIA_PLAYER, "off", {ATTR_ENTITY_PICTURE: "/local/tv.png"}
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_media_image_relative_url(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a relative media image url is fetched from Home Assistant."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {"media_image_url": _attribute_template("media_image_url")},
        STATE_TEMPLATE,
    )
    # Images are cached across tests by url, so each style needs its own.
    image_path = f"/local/art_{style.name.lower()}.png"
    await async_trigger(
        hass, TEST_STATE_ENTITY_ID, "playing", {"media_image_url": image_path}
    )
    aioclient_mock.get(
        f"http://example.local:8123{image_path}",
        content=b"art",
        headers={"Content-Type": "image/png"},
    )
    state = hass.states.get(TEST_MEDIA_PLAYER.entity_id)
    client = await hass_client_no_auth()

    resp = await client.get(state.attributes[ATTR_ENTITY_PICTURE])
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"art"
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("config", "expected_features"),
    [
        pytest.param({}, MediaPlayerEntityFeature(0), id="no_actions"),
        pytest.param(
            ON_OFF_ACTIONS,
            MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF,
            id="on_off",
        ),
        pytest.param(
            {**make_test_action("volume_up"), **make_test_action("volume_down")},
            MediaPlayerEntityFeature.VOLUME_STEP,
            id="volume_step",
        ),
        pytest.param(
            {**make_test_action("select_source"), **SOURCE_LIST},
            MediaPlayerEntityFeature.SELECT_SOURCE,
            id="select_source",
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    expected_features: MediaPlayerEntityFeature,
) -> None:
    """Test supported features are derived from the configured actions."""
    await setup_entity(hass, TEST_MEDIA_PLAYER, style, 1, config, STATE_TEMPLATE)
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "on")
    assert_state_and_attributes(
        hass, TEST_MEDIA_PLAYER, "on", {ATTR_SUPPORTED_FEATURES: expected_features}
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("action", "extra_config", "service", "service_data", "expected_variables"),
    [
        pytest.param("turn_on", {}, "turn_on", {}, {}, id="turn_on"),
        pytest.param("turn_off", {}, "turn_off", {}, {}, id="turn_off"),
        pytest.param("media_play", {}, "media_play", {}, {}, id="media_play"),
        pytest.param("media_pause", {}, "media_pause", {}, {}, id="media_pause"),
        pytest.param("media_stop", {}, "media_stop", {}, {}, id="media_stop"),
        pytest.param(
            "media_next_track", {}, "media_next_track", {}, {}, id="next_track"
        ),
        pytest.param(
            "media_previous_track",
            {},
            "media_previous_track",
            {},
            {},
            id="previous_track",
        ),
        pytest.param(
            "clear_playlist", {}, "clear_playlist", {}, {}, id="clear_playlist"
        ),
        pytest.param(
            "volume_up",
            make_test_action("volume_down"),
            "volume_up",
            {},
            {},
            id="volume_up",
        ),
        pytest.param(
            "volume_down",
            make_test_action("volume_up"),
            "volume_down",
            {},
            {},
            id="volume_down",
        ),
        pytest.param(
            "media_seek",
            {},
            "media_seek",
            {"seek_position": 30},
            {"seek_position": 30},
            id="media_seek",
        ),
        pytest.param(
            "volume_set",
            {},
            "volume_set",
            {"volume_level": 0.3},
            {"volume_level": 0.3},
            id="volume_set",
        ),
        pytest.param(
            "volume_mute",
            {},
            "volume_mute",
            {"is_volume_muted": True},
            {"is_volume_muted": True},
            id="volume_mute",
        ),
        pytest.param(
            "shuffle_set",
            {},
            "shuffle_set",
            {"shuffle": True},
            {"shuffle": True},
            id="shuffle_set",
        ),
        pytest.param(
            "repeat_set",
            {},
            "repeat_set",
            {"repeat": "all"},
            {"repeat": "all"},
            id="repeat_set",
        ),
        pytest.param(
            "select_source",
            SOURCE_LIST,
            "select_source",
            {"source": "Radio"},
            {"source": "Radio"},
            id="select_source",
        ),
        pytest.param(
            "select_sound_mode",
            SOUND_MODE_LIST,
            "select_sound_mode",
            {"sound_mode": "Music"},
            {"sound_mode": "Music"},
            id="select_sound_mode",
        ),
        pytest.param(
            "play_media",
            {},
            "play_media",
            {"media_content_type": "music", "media_content_id": "abc"},
            {"media_content_type": "music", "media_content_id": "abc"},
            id="play_media",
        ),
    ],
)
async def test_actions(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
    action: str,
    extra_config: ConfigType,
    service: str,
    service_data: ConfigType,
    expected_variables: ConfigType,
) -> None:
    """Test actions run their script with the service data as variables."""
    script_data = {key: f"{{{{ {key} }}}}" for key in expected_variables}
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {**make_test_action(action, script_data), **extra_config},
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing")

    await hass.services.async_call(
        media_player.DOMAIN,
        service,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id, **service_data},
        blocking=True,
    )
    assert_action(TEST_MEDIA_PLAYER, calls, 1, action, **expected_variables)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("service", "expected_volume"),
    [
        pytest.param("volume_up", 0.6, id="volume_up"),
        pytest.param("volume_down", 0.4, id="volume_down"),
    ],
)
async def test_volume_step_falls_back_to_volume_set(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
    service: str,
    expected_volume: float,
) -> None:
    """Test volume up and down use volume_set when they have no action."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {
            "volume_level": "{{ 0.5 }}",
            **make_test_action("volume_set", {"volume_level": "{{ volume_level }}"}),
        },
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing")

    await hass.services.async_call(
        media_player.DOMAIN,
        service,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id},
        blocking=True,
    )
    assert_action(TEST_MEDIA_PLAYER, calls, 1, "volume_set")
    assert calls[-1].data["volume_level"] == pytest.approx(expected_volume)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        pytest.param("turn_on", MediaPlayerState.ON, id="turn_on"),
        pytest.param("turn_off", MediaPlayerState.OFF, id="turn_off"),
        pytest.param("media_play", MediaPlayerState.PLAYING, id="media_play"),
        pytest.param("media_pause", MediaPlayerState.PAUSED, id="media_pause"),
        pytest.param("media_stop", MediaPlayerState.IDLE, id="media_stop"),
    ],
)
async def test_optimistic_state(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
    service: str,
    expected_state: MediaPlayerState,
) -> None:
    """Test the state is assumed when there is no state template."""
    await setup_entity(
        hass, TEST_MEDIA_PLAYER, style, 1, {**ON_OFF_ACTIONS, **PLAYBACK_ACTIONS}
    )
    state = assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, STATE_UNKNOWN)
    assert state.attributes["assumed_state"] is True

    await hass.services.async_call(
        media_player.DOMAIN,
        service,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id},
        blocking=True,
    )
    assert_action(TEST_MEDIA_PLAYER, calls, 1, service)
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, expected_state)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_state_template_is_not_optimistic(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
) -> None:
    """Test the state follows the template instead of the action."""
    await setup_entity(
        hass, TEST_MEDIA_PLAYER, style, 1, PLAYBACK_ACTIONS, STATE_TEMPLATE
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "paused")

    await hass.services.async_call(
        media_player.DOMAIN,
        "media_play",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id},
        blocking=True,
    )
    assert_action(TEST_MEDIA_PLAYER, calls, 1, "media_play")
    state = assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, "paused")
    assert "assumed_state" not in state.attributes


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("action", "extra_config", "service", "service_data", "attribute", "expected"),
    [
        pytest.param(
            "volume_set",
            {},
            "volume_set",
            {"volume_level": 0.3},
            "volume_level",
            0.3,
            id="volume_level",
        ),
        pytest.param(
            "volume_mute",
            {},
            "volume_mute",
            {"is_volume_muted": True},
            "is_volume_muted",
            True,
            id="is_volume_muted",
        ),
        pytest.param(
            "shuffle_set",
            {},
            "shuffle_set",
            {"shuffle": True},
            "shuffle",
            True,
            id="shuffle",
        ),
        pytest.param(
            "repeat_set",
            {},
            "repeat_set",
            {"repeat": "one"},
            "repeat",
            "one",
            id="repeat",
        ),
        pytest.param(
            "select_source",
            SOURCE_LIST,
            "select_source",
            {"source": "Radio"},
            "source",
            "Radio",
            id="source",
        ),
        pytest.param(
            "select_sound_mode",
            SOUND_MODE_LIST,
            "select_sound_mode",
            {"sound_mode": "Music"},
            "sound_mode",
            "Music",
            id="sound_mode",
        ),
    ],
)
async def test_optimistic_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
    action: str,
    extra_config: ConfigType,
    service: str,
    service_data: ConfigType,
    attribute: str,
    expected: Any,
) -> None:
    """Test attributes are assumed when they have an action but no template."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {**make_test_action(action), **extra_config},
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing")

    await hass.services.async_call(
        media_player.DOMAIN,
        service,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id, **service_data},
        blocking=True,
    )
    assert_action(TEST_MEDIA_PLAYER, calls, 1, action)
    assert_state_and_attributes(
        hass, TEST_MEDIA_PLAYER, "playing", {attribute: expected}
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("action", "template_config", "service", "service_data", "attribute", "expected"),
    [
        pytest.param(
            "volume_set",
            {"volume_level": "{{ 0.5 }}"},
            "volume_set",
            {"volume_level": 0.3},
            "volume_level",
            0.5,
            id="volume_level",
        ),
        pytest.param(
            "volume_mute",
            {"is_volume_muted": "{{ False }}"},
            "volume_mute",
            {"is_volume_muted": True},
            "is_volume_muted",
            False,
            id="is_volume_muted",
        ),
        pytest.param(
            "shuffle_set",
            {"shuffle": "{{ False }}"},
            "shuffle_set",
            {"shuffle": True},
            "shuffle",
            False,
            id="shuffle",
        ),
        pytest.param(
            "repeat_set",
            {"repeat": "{{ 'off' }}"},
            "repeat_set",
            {"repeat": "one"},
            "repeat",
            "off",
            id="repeat",
        ),
        pytest.param(
            "select_source",
            {"source": "{{ 'TV' }}", **SOURCE_LIST},
            "select_source",
            {"source": "Radio"},
            "source",
            "TV",
            id="source",
        ),
        pytest.param(
            "select_sound_mode",
            {"sound_mode": "{{ 'Movie' }}", **SOUND_MODE_LIST},
            "select_sound_mode",
            {"sound_mode": "Music"},
            "sound_mode",
            "Movie",
            id="sound_mode",
        ),
    ],
)
async def test_templated_attributes_are_not_optimistic(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
    action: str,
    template_config: ConfigType,
    service: str,
    service_data: ConfigType,
    attribute: str,
    expected: Any,
) -> None:
    """Test attributes follow their template instead of the action."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {**make_test_action(action), **template_config},
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing")

    await hass.services.async_call(
        media_player.DOMAIN,
        service,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id, **service_data},
        blocking=True,
    )
    assert_action(TEST_MEDIA_PLAYER, calls, 1, action)
    assert_state_and_attributes(
        hass, TEST_MEDIA_PLAYER, "playing", {attribute: expected}
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"source": "{{ 'TV' }}"}, id="source_without_list"),
        pytest.param(make_test_action("select_source"), id="select_source"),
        pytest.param({"sound_mode": "{{ 'Movie' }}"}, id="sound_mode_without_list"),
        pytest.param(make_test_action("select_sound_mode"), id="select_sound_mode"),
        pytest.param(make_test_action("volume_up"), id="volume_up_without_down"),
        pytest.param(make_test_action("volume_down"), id="volume_down_without_up"),
    ],
)
async def test_option_requires_option(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
) -> None:
    """Test options are rejected without the option they depend on."""
    await setup_entity(hass, TEST_MEDIA_PLAYER, style, 0, config, STATE_TEMPLATE)
    assert hass.states.async_all(media_player.DOMAIN) == []


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("option", "list_option", "value"),
    [
        pytest.param("source", "source_list", "TV", id="source"),
        pytest.param("sound_mode", "sound_mode_list", "Movie", id="sound_mode"),
    ],
)
async def test_selection_revalidated_on_list_change(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    option: str,
    list_option: str,
    value: str,
) -> None:
    """Test an unchanged selection becomes valid when its list later includes it."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {
            option: _attribute_template(option),
            list_option: f"{{{{ state_attr('{TEST_STATE_ENTITY_ID}', '{list_option}')"
            " or [] }}",
        },
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "on", {option: value})
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, "on", {option: None})

    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "on",
        {option: value, list_option: [value, "Other"]},
    )
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, "on", {option: value})

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "on", {option: value})
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, "on", {option: None})


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_availability_template(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test the availability template."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {"availability": f"{{{{ is_state('{TEST_AVAILABILITY_ENTITY_ID}', 'on') }}}}"},
        "{{ 'playing' }}",
    )
    await async_trigger(hass, TEST_AVAILABILITY_ENTITY_ID, "off")
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, STATE_UNAVAILABLE)

    await async_trigger(hass, TEST_AVAILABILITY_ENTITY_ID, "on")
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, MediaPlayerState.PLAYING)


async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an invalid availability template keeps the media player available."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        ConfigurationStyle.MODERN,
        1,
        {"availability": "{{ x - 12 }}"},
        "{{ 'playing' }}",
    )
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, MediaPlayerState.PLAYING)
    assert "UndefinedError: 'x' is undefined" in caplog.text


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_device_class(hass: HomeAssistant, style: ConfigurationStyle) -> None:
    """Test the device class."""
    await setup_entity(
        hass, TEST_MEDIA_PLAYER, style, 1, {"device_class": "tv"}, STATE_TEMPLATE
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "on")
    assert_state_and_attributes(hass, TEST_MEDIA_PLAYER, "on", {"device_class": "tv"})


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("saved_state", "saved_extra_data", "initial_state", "initial_attributes"),
    [
        pytest.param(
            "playing",
            {
                **NO_MEDIA_DATA,
                "is_volume_muted": True,
                "repeat": "all",
                "shuffle": True,
                "sound_mode": "Music",
                "sound_mode_list": ["Movie", "Music"],
                "source": "Radio",
                "source_list": ["TV", "Radio"],
                "volume_level": 0.4,
            },
            "playing",
            {
                "volume_level": 0.4,
                "is_volume_muted": True,
                "repeat": "all",
                "shuffle": True,
                "sound_mode": "Music",
                "sound_mode_list": ["Movie", "Music"],
                "source": "Radio",
                "source_list": ["TV", "Radio"],
            },
            id="restored",
        ),
        pytest.param("playing", None, STATE_UNKNOWN, {}, id="no_extra_data"),
        pytest.param(
            "playing",
            {
                **NO_MEDIA_DATA,
                "is_volume_muted": None,
                "repeat": "never",
                "shuffle": None,
                "sound_mode": None,
                "sound_mode_list": None,
                "source": None,
                "source_list": None,
                "volume_level": None,
            },
            STATE_UNKNOWN,
            {},
            id="invalid_extra_data",
        ),
        pytest.param(
            "standby",
            {
                **NO_MEDIA_DATA,
                "is_volume_muted": None,
                "repeat": None,
                "shuffle": None,
                "sound_mode": None,
                "sound_mode_list": None,
                "source": None,
                "source_list": None,
                "volume_level": None,
            },
            STATE_UNKNOWN,
            {},
            id="deprecated_state",
        ),
    ],
)
async def test_restore_state(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    saved_state: str,
    saved_extra_data: ConfigType | None,
    initial_state: str,
    initial_attributes: ConfigType,
) -> None:
    """Test restoring an optimistic template media player."""
    setup_mock_template_entity_restore_state(
        hass,
        TEST_MEDIA_PLAYER,
        saved_state,
        saved_extra_data=saved_extra_data,
    )
    await setup_restore_template_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        {
            **ON_OFF_ACTIONS,
            **make_test_action("volume_set"),
            **make_test_action("volume_mute"),
            **make_test_action("repeat_set"),
            **make_test_action("shuffle_set"),
            **make_test_action("select_source"),
            **make_test_action("select_sound_mode"),
            **SOURCE_LIST,
            **SOUND_MODE_LIST,
        },
    )
    assert_state_and_attributes(
        hass, TEST_MEDIA_PLAYER, initial_state, initial_attributes
    )


@pytest.mark.usefixtures("calls")
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_restore_state_is_saved(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test the optimistic state and attributes are saved for restoring."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {
            **PLAYBACK_ACTIONS,
            **make_test_action("repeat_set"),
            **make_test_action("select_source"),
            **SOURCE_LIST,
        },
    )
    # Trigger entities only render the source list once triggered.
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "on")
    for service, data in (
        ("media_play", {}),
        ("repeat_set", {"repeat": "all"}),
        ("select_source", {"source": "Radio"}),
    ):
        await hass.services.async_call(
            media_player.DOMAIN,
            service,
            {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER.entity_id, **data},
            blocking=True,
        )

    restore_data = await async_mock_restore_state_shutdown_restart(hass)
    stored = restore_data.last_states_by_entity_id[TEST_MEDIA_PLAYER.entity_id]
    assert stored.state.state == MediaPlayerState.PLAYING
    assert stored.extra_data.as_dict() == {
        **NO_MEDIA_DATA,
        "is_volume_muted": None,
        "repeat": "all",
        "shuffle": None,
        "sound_mode": None,
        "sound_mode_list": None,
        "source": "Radio",
        "source_list": ["TV", "Radio"],
        "volume_level": None,
    }


async def test_media_position_sample_after_template_error(
    hass: HomeAssistant,
) -> None:
    """Test a repeated position sample is applied after a template error cleared it."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        ConfigurationStyle.MODERN,
        1,
        {
            "media_position": (
                f"{{{{ state_attr('{TEST_STATE_ENTITY_ID}', 'media_position') + 0 }}}}"
            )
        },
        STATE_TEMPLATE,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing", {"media_position": 30})

    # A missing attribute makes the template raise, which clears the position.
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing")
    assert_state_and_attributes(
        hass, TEST_MEDIA_PLAYER, "playing", {"media_position": None}
    )

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing", {"media_position": 30})
    assert_state_and_attributes(
        hass, TEST_MEDIA_PLAYER, "playing", {"media_position": 30}
    )


async def test_restored_media_position_cleared_by_empty_sample(
    hass: HomeAssistant,
) -> None:
    """Test the first empty position sample clears a restored position."""
    setup_mock_template_entity_restore_state(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        saved_extra_data={
            "is_volume_muted": None,
            "media": {**NO_MEDIA_DATA["media"], "media_position": 30},
            "media_position_updated_at": "2026-10-17T00:00:00+00:00",
            "repeat": None,
            "shuffle": None,
            "sound_mode": None,
            "sound_mode_list": None,
            "source": None,
            "source_list": None,
            "volume_level": None,
        },
    )
    await setup_restore_template_entity(
        hass,
        TEST_MEDIA_PLAYER,
        ConfigurationStyle.TRIGGER,
        {
            "state": STATE_TEMPLATE,
            "media_position": _attribute_template("media_position"),
        },
    )
    assert_state_and_attributes(
        hass, TEST_MEDIA_PLAYER, "playing", {"media_position": 30}
    )

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "playing")
    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        {"media_position": None, "media_position_updated_at": None},
    )


async def test_restore_media_metadata_trigger(hass: HomeAssistant) -> None:
    """Test media metadata is restored before a trigger entity renders."""
    saved_media = {
        **NO_MEDIA_DATA["media"],
        "media_content_id": "song-1",
        "media_duration": 300,
        "media_image_url": "/local/art.png",
        "media_position": 30,
        "media_title": "Song",
    }
    setup_mock_template_entity_restore_state(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        saved_extra_data={
            "is_volume_muted": None,
            "media": saved_media,
            "media_position_updated_at": "2026-10-17T00:00:00+00:00",
            "repeat": None,
            "shuffle": None,
            "sound_mode": None,
            "sound_mode_list": None,
            "source": None,
            "source_list": None,
            "volume_level": None,
        },
    )
    await setup_restore_template_entity(
        hass,
        TEST_MEDIA_PLAYER,
        ConfigurationStyle.TRIGGER,
        {
            "state": STATE_TEMPLATE,
            **{
                option: _attribute_template(option)
                for option in (
                    "media_content_id",
                    "media_duration",
                    "media_image_url",
                    "media_position",
                    "media_title",
                )
            },
        },
    )

    assert_state_and_attributes(
        hass,
        TEST_MEDIA_PLAYER,
        "playing",
        {
            "media_content_id": "song-1",
            "media_duration": 300,
            "media_position": 30,
            "media_position_updated_at": dt_util.parse_datetime(
                "2026-10-17T00:00:00+00:00"
            ),
            "media_title": "Song",
        },
    )
    state = hass.states.get(TEST_MEDIA_PLAYER.entity_id)
    assert state.attributes[ATTR_ENTITY_PICTURE].startswith(
        f"/api/media_player_proxy/{TEST_MEDIA_PLAYER.entity_id}?token="
    )


@pytest.mark.usefixtures("calls")
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_restore_media_metadata_is_saved(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test media metadata and the position timestamp are saved for restoring."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {
            "media_title": _attribute_template("media_title"),
            "media_position": _attribute_template("media_position"),
        },
        STATE_TEMPLATE,
    )
    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "playing",
        {"media_title": "Song", "media_position": 30},
    )

    restore_data = await async_mock_restore_state_shutdown_restart(hass)
    stored = restore_data.last_states_by_entity_id[TEST_MEDIA_PLAYER.entity_id]
    assert stored.extra_data.as_dict()["media"] == {
        **NO_MEDIA_DATA["media"],
        "media_position": 30,
        "media_title": "Song",
    }
    assert (
        stored.extra_data.as_dict()["media_position_updated_at"]
        == dt_util.utcnow().isoformat()
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_unique_id(hass: HomeAssistant, style: ConfigurationStyle) -> None:
    """Test unique_id option only creates one media player per id."""
    await setup_and_test_unique_id(hass, TEST_MEDIA_PLAYER, style, ON_OFF_ACTIONS)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to media player unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_MEDIA_PLAYER, style, entity_registry, ON_OFF_ACTIONS
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize("action", ["turn_on", "media_play", "volume_set"])
async def test_invalid_yaml_actions_do_not_create_entities(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    action: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid yaml actions do not create entities."""
    await assert_invalid_yaml_actions_do_not_create_entities(
        hass, TEST_MEDIA_PLAYER, style, {}, action, caplog
    )


@pytest.mark.parametrize(
    ("action", "config"),
    [
        pytest.param("turn_on", {}, id="turn_on"),
        pytest.param("media_play", {}, id="media_play"),
        pytest.param("volume_set", {}, id="volume_set"),
        pytest.param("select_source", SOURCE_LIST, id="select_source"),
    ],
)
async def test_invalid_config_entry_actions_do_not_create_entities(
    hass: HomeAssistant,
    action: str,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid config entry actions do not create entities."""
    await assert_invalid_config_entry_actions_do_not_create_entities(
        hass, TEST_MEDIA_PLAYER, config, action, caplog
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_extra_template_attributes(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test extra attributes."""
    await assert_extra_template_attributes(
        hass, TEST_MEDIA_PLAYER, style, {"state": "{{ 'on' }}"}
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_attributes_template(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes as a single template."""
    await assert_attributes_template(
        hass, TEST_MEDIA_PLAYER, style, {"state": "{{ 'on' }}"}, caplog
    )


@pytest.mark.parametrize(
    "attribute",
    [
        *chain(MediaPlayerEntityCapabilityAttribute, MediaPlayerEntityStateAttribute),
        "device_class",
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_blocked_template_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute: StrEnum | str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test blocked extra attributes."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        0,
        {
            "state": "{{ 'on' }}",
            "attributes": {str(attribute): "{{ 'does not matter' }}"},
        },
    )
    assert (
        f"Unsupported attribute(s) found for {DEFAULT_NAME}: {attribute}" in caplog.text
    )


@pytest.mark.parametrize(
    "attribute",
    [
        *chain(MediaPlayerEntityCapabilityAttribute, MediaPlayerEntityStateAttribute),
        "device_class",
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_attributes_template_with_blocked_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute: StrEnum | str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test blocked attributes for a single attributes template."""
    await setup_entity(
        hass,
        TEST_MEDIA_PLAYER,
        style,
        1,
        {
            "state": "{{ 'on' }}",
            "attributes": f"{{{{ dict({attribute}='does not matter') }}}}",
        },
    )

    await async_trigger(hass, "sensor.test_extra_attributes", "anything")

    error = (
        f"Unsupported attribute(s) found for {TEST_MEDIA_PLAYER.entity_id}: {attribute}"
    )
    assert error in caplog.text


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a media player from a config entry."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, "playing")

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "template_type": media_player.DOMAIN,
            "state": STATE_TEMPLATE,
            "device_class": "tv",
            "volume_level": "{{ 0.5 }}",
            "source": "{{ 'TV' }}",
            "source_list": "{{ ['TV', 'Radio'] }}",
            **ON_OFF_ACTIONS,
            **make_test_action("volume_set"),
            **make_test_action("volume_up"),
            **make_test_action("volume_down"),
            **make_test_action("select_source"),
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.my_template")
    assert state is not None
    assert state == snapshot


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""
    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        media_player.DOMAIN,
        {
            "name": "My template",
            "state": "{{ 'playing' }}",
            "source": "{{ 'TV' }}",
            "source_list": "{{ ['TV', 'Radio'] }}",
        },
    )

    assert state["state"] == MediaPlayerState.PLAYING
    assert state["attributes"]["source"] == "TV"
