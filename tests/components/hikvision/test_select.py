"""Test Hikvision image setting selects."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
import threading
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyhik.image import (
    ImageSetting,
    ImageSettingType,
    ImageWriteResult,
    parse_image_capabilities,
    parse_image_values,
)
from pyhik.isapi import ISAPIError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hikvision.const import (
    DOMAIN,
    EVENT_IMAGE_SETTING_CHANGED,
    IMAGE_SELECT_SETTINGS,
)
from homeassistant.components.hikvision.coordinator import SCAN_INTERVAL
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from . import image_channel_with, setup_integration
from .conftest import TEST_DEVICE_ID

SHUTTER = "select.front_camera_shutter_speed"
DAY_NIGHT = "select.front_camera_day_night_mode"
WDR = "select.front_camera_wdr"
BLC_MODE = "select.front_camera_backlight_compensation_mode"
HLC_MODE = "select.front_camera_highlight_compensation_mode"
FLIP_DIRECTION = "select.front_camera_flip_direction"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load during test."""
    return [Platform.SELECT]


def _use_settings(
    mock_image_settings: MagicMock,
    settings: list[ImageSetting],
    values: dict[str, str],
) -> None:
    mock_image_settings.get_image_settings.return_value = settings
    mock_image_settings.get_image_values.return_value = values


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_hikcamera", "mock_image_settings"
)
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all select entities of a camera."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("key", "path", "camera_options", "options", "enabled"),
    [
        (
            "day_night_schedule_type",
            "IrcutFilter/Schedule/scheduleType",
            "day,night",
            ["day", "night"],
            False,
        ),
        (
            "p_iris_mode",
            "Exposure/pIris/pIrisType",
            "auto,manual",
            ["auto", "manual"],
            False,
        ),
        # Shown as the camera reports them.
        (
            "max_shutter_speed",
            "Shutter/maxShutterLevelLimit",
            "1/25,1/50,1/100",
            ["1/25", "1/50", "1/100"],
            False,
        ),
        (
            "min_shutter_speed",
            "Shutter/minShutterLevelLimit",
            "1/25,1/50,1/100",
            ["1/25", "1/50", "1/100"],
            False,
        ),
        ("iris_level", "Iris/IrisLevel", "F1.6,F2.0", ["F1.6", "F2.0"], False),
        (
            "color_mode",
            "Color/grayScale/grayScaleMode",
            "indoor,outdoor",
            ["indoor", "outdoor"],
            False,
        ),
        (
            "defog",
            "Dehaze/DehazeMode",
            "open,close,auto",
            ["open", "close", "auto"],
            False,
        ),
        (
            "supplement_light",
            "SupplementLight/supplementLightMode",
            "eventIntelligence,irLight,colorVuWhiteLight,close",
            ["eventintelligence", "irlight", "colorvuwhitelight", "close"],
            True,
        ),
        (
            "supplement_light_mode",
            "SupplementLight/mode",
            "auto,manual",
            ["auto", "manual"],
            False,
        ),
        (
            "light_brightness_mode",
            "SupplementLight/mixedLightBrightnessRegulatMode",
            "auto,manual",
            ["auto", "manual"],
            True,
        ),
        (
            "event_intelligence_brightness_mode",
            "SupplementLight/EventIntelligenceModeCfg/brightnessRegulatMode",
            "auto,manual",
            ["auto", "manual"],
            False,
        ),
        ("ir_light_mode", "IrLight/mode", "auto,manual", ["auto", "manual"], False),
        (
            "focus_mode",
            "FocusConfiguration/focusStyle",
            "AUTO,MANUAL,SEMIAUTOMATIC",
            ["auto", "manual", "semiautomatic"],
            False,
        ),
        (
            "focus_distance_mode",
            "FocusConfiguration/focusDistanceMode",
            "compatible,manual",
            ["compatible", "manual"],
            False,
        ),
        (
            "focus_limit_mode",
            "FocusConfiguration/focusLimited",
            "10,50,100",
            ["10", "50", "100"],
            False,
        ),
        (
            "digital_slow_shutter_level",
            "DSS/DSSLevel",
            "auto,1.25,1.5,2",
            ["auto", "1_25", "1_5", "2"],
            False,
        ),
        (
            "zoom_limit_ratio",
            "ZoomLimit/ZoomLimitRatio",
            "1,2,4",
            ["1", "2", "4"],
            False,
        ),
        (
            "capture_mode",
            "CaptureMode/mode",
            "1920*1080@30fps,close",
            ["1920_1080_30fps", "close"],
            False,
        ),
    ],
)
async def test_selects_the_fixture_camera_does_not_have(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
    key: str,
    path: str,
    camera_options: str,
    options: list[str],
    enabled: bool,
) -> None:
    """Test each select is found from the capabilities, and writes its own path.

    The camera's value for the option chosen is what is written.
    """
    first, *_, last = camera_options.split(",")
    translated = next(
        setting.translate_options
        for setting in IMAGE_SELECT_SETTINGS
        if setting.key == key
    )
    capabilities = image_channel_with(path, f' opt="{camera_options}">{first}')
    values = image_channel_with(path, f">{first}")
    _use_settings(
        mock_image_settings,
        parse_image_capabilities(capabilities, values),
        parse_image_values(values),
    )

    await setup_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        SELECT_DOMAIN, DOMAIN, f"{TEST_DEVICE_ID}_image_{key}"
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry.translation_key == key
    assert entry.entity_category is EntityCategory.CONFIG
    assert er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ) == [entry]
    assert entry.disabled_by is (
        None if enabled else er.RegistryEntryDisabler.INTEGRATION
    )
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == options[0]
    assert state.attributes[ATTR_OPTIONS] == options
    # A translated option has a name, not only the ones the test camera has.
    translations = await async_get_translations(hass, "en", "entity", [DOMAIN])
    assert [
        option
        for option in options
        if translated
        and f"component.{DOMAIN}.entity.select.{key}.state.{option}" not in translations
    ] == []

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: options[-1]},
        blocking=True,
    )
    mock_image_settings.set_image_setting.assert_called_once_with(path, last)


@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_enabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only the commonly used selects are enabled by default."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(DAY_NIGHT).state == "night"
    assert hass.states.get(SHUTTER).state == "1/1000"
    assert hass.states.get(FLIP_DIRECTION) is None
    assert (
        entity_registry.async_get(FLIP_DIRECTION).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test named options are lowercase keys and numeric ones are left as they are."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(WDR).attributes[ATTR_OPTIONS] == ["close", "open", "auto"]
    assert hass.states.get(BLC_MODE).attributes[ATTR_OPTIONS] == [
        "close",
        "up",
        "down",
        "left",
        "right",
        "center",
        "region",
        "auto",
    ]
    assert hass.states.get(SHUTTER).attributes[ATTR_OPTIONS][:3] == [
        "1/3",
        "1/6",
        "1/12",
    ]


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("entity_id", "option", "path", "value"),
    [
        (SHUTTER, "1/500", "Shutter/ShutterLevel", "1/500"),
        (DAY_NIGHT, "auto", "IrcutFilter/IrcutFilterType", "auto"),
        (WDR, "open", "WDR/mode", "open"),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
    entity_id: str,
    option: str,
    path: str,
    value: str,
) -> None:
    """Test choosing an option writes the camera's value."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.get_image_values.return_value = {**image_values, path: value}

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    mock_image_settings.set_image_setting.assert_called_once_with(path, value)
    assert hass.states.get(entity_id).state == option


@pytest.mark.usefixtures("mock_hikcamera")
async def test_option_is_written_with_the_cameras_spelling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a lowercase option is turned back into the value the camera uses."""
    _use_settings(
        mock_image_settings,
        [
            ImageSetting(
                "IrcutFilter/IrcutFilterType",
                ImageSettingType.SELECT,
                options=["day", "night", "auto", "schedule", "eventTrigger"],
                value="day",
            )
        ],
        {"IrcutFilter/IrcutFilterType": "day"},
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(DAY_NIGHT).attributes[ATTR_OPTIONS][-1] == "eventtrigger"
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: DAY_NIGHT, ATTR_OPTION: "eventtrigger"},
        blocking=True,
    )

    mock_image_settings.set_image_setting.assert_called_once_with(
        "IrcutFilter/IrcutFilterType", "eventTrigger"
    )


@pytest.mark.usefixtures("mock_hikcamera")
async def test_linked_mode_is_changed_together_with_its_enabled_flag(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test a mode that has an enabled flag, such as BLC, is written as a pair."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(BLC_MODE).state == "auto"
    mock_image_settings.get_image_values.return_value = {
        **image_values,
        "BLC/BLCMode": "UP",
    }

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: BLC_MODE, ATTR_OPTION: "up"},
        blocking=True,
    )

    setting, value = mock_image_settings.set_image_linked_setting.call_args.args
    assert (setting.path, setting.linked_enabled_path, value) == (
        "BLC/BLCMode",
        "BLC/enabled",
        "UP",
    )
    mock_image_settings.set_image_setting.assert_not_called()
    assert hass.states.get(BLC_MODE).state == "up"


@pytest.mark.usefixtures("mock_hikcamera")
async def test_highlight_compensation_mode_linked_to_its_enabled_flag(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test firmware with an HLC mode gets a select, since pyhik merges it with HLC/enabled."""
    hlc_mode = ImageSetting(
        "HLC/HLCMode",
        ImageSettingType.SELECT,
        options=["close", "open", "auto"],
        linked_enabled_path="HLC/enabled",
        off_value="close",
    )
    _use_settings(mock_image_settings, [hlc_mode], {"HLC/enabled": "false"})
    caplog.set_level(logging.DEBUG, "homeassistant.components.hikvision")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(HLC_MODE)
    assert state.state == "close"
    assert state.attributes["options"] == ["close", "open", "auto"]

    mock_image_settings.get_image_values.return_value = {
        "HLC/enabled": "true",
        "HLC/HLCMode": "auto",
    }
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: HLC_MODE, ATTR_OPTION: "auto"},
        blocking=True,
    )

    mock_image_settings.set_image_linked_setting.assert_called_once_with(
        hlc_mode, "auto"
    )
    assert hass.states.get(HLC_MODE).state == "auto"
    # Both settings the write changed are logged.
    assert "setting HLC/HLCMode to auto, HLC/enabled to true" in caplog.text
    assert "set HLC/HLCMode to auto, HLC/enabled to true (status 200, ok)" in (
        caplog.text
    )


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("values", "expected"),
    [
        # The camera does not say whether the feature is on, so the mode is shown.
        ({"HLC/HLCMode": "auto"}, "auto"),
        # Neither is reported: the camera does not have them now.
        ({}, STATE_UNAVAILABLE),
        ({"HLC/enabled": "false"}, "close"),
        ({"HLC/enabled": "FALSE", "HLC/HLCMode": "auto"}, "close"),
        # A flag that is neither true nor false says nothing either.
        ({"HLC/enabled": "1", "HLC/HLCMode": "auto"}, "auto"),
        ({"HLC/enabled": "", "HLC/HLCMode": "auto"}, "auto"),
    ],
)
async def test_linked_mode_without_an_enabled_flag(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    values: dict[str, str],
    expected: str,
) -> None:
    """Test only an enabled flag that is false is read as off."""
    hlc_mode = ImageSetting(
        "HLC/HLCMode",
        ImageSettingType.SELECT,
        options=["close", "open", "auto"],
        linked_enabled_path="HLC/enabled",
        off_value="close",
    )
    _use_settings(mock_image_settings, [hlc_mode], values)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(HLC_MODE).state == expected


@pytest.mark.usefixtures("mock_hikcamera")
async def test_linked_flag_is_logged_for_its_mode_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test BLC/enabled is reported for the BLC mode, the entity it belongs to."""
    await setup_integration(hass, mock_config_entry)
    events = async_capture_events(hass, EVENT_IMAGE_SETTING_CHANGED)
    context = Context()
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        True, 200, "ok", {"BLC/enabled": "false"}
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SHUTTER, ATTR_OPTION: "1/500"},
        blocking=True,
        context=context,
    )

    assert [(e.data["name"], e.data.get("entity_id")) for e in events] == [
        ("Front Camera Backlight compensation mode", BLC_MODE)
    ]
    assert events[0].data["message"] == (
        "was turned off automatically so that Front Camera Shutter speed could be"
        " changed"
    )
    # The entry belongs to the action that asked for the change.
    assert events[0].context.id == context.id


@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_no_link_to_an_entity_this_setup_did_not_add(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test only an entity that is in Home Assistant is linked to.

    Not a disabled one, nor a registry entry left by an earlier setup: the path
    stands in for the name, as the camera's settings spell it.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    entity_registry.async_get_or_create(
        SELECT_DOMAIN,
        "hikvision",
        f"{mock_config_entry.runtime_data.device_id}_image_old_setting",
        suggested_object_id="old_setting",
    )
    # Disabled by default.
    assert hass.states.get(FLIP_DIRECTION) is None

    assert coordinator._async_entity_name("old/setting") == ("old/setting", None)
    assert coordinator._async_entity_name("imageflip/imageflipstyle") == (
        "ImageFlip/ImageFlipStyle",
        None,
    )
    assert coordinator._async_entity_name("wdr/MODE") == ("Front Camera WDR", WDR)


@pytest.mark.usefixtures("mock_hikcamera")
async def test_linked_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test turning a linked mode off, and that it then reads as off."""
    await setup_integration(hass, mock_config_entry)
    # The camera leaves the mode out while the feature is off.
    off_values = {
        key: value for key, value in image_values.items() if key != "BLC/BLCMode"
    }
    off_values["BLC/enabled"] = "false"
    mock_image_settings.get_image_values.return_value = off_values

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: BLC_MODE, ATTR_OPTION: "close"},
        blocking=True,
    )

    assert mock_image_settings.set_image_linked_setting.call_args.args[1] == "CLOSE"
    assert hass.states.get(BLC_MODE).state == "close"


@pytest.mark.usefixtures("mock_hikcamera")
async def test_firmware_that_reports_the_blc_flag_as_a_choice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a camera that lists a misspelled "true" for BLC (a firmware typo)."""
    _use_settings(
        mock_image_settings,
        [
            ImageSetting(
                "BLC/enabled",
                ImageSettingType.SELECT,
                options=["ture", "false"],  # codespell:ignore ture
                value="false",
            )
        ],
        {"BLC/enabled": "false"},
    )
    await setup_integration(hass, mock_config_entry)
    entity_id = "select.front_camera_backlight_compensation"

    assert hass.states.get(entity_id).state == "false"
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "ture"},  # codespell:ignore ture
        blocking=True,
    )

    mock_image_settings.set_image_setting.assert_called_once_with(
        "BLC/enabled",
        "ture",  # codespell:ignore ture
    )


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("extra", "state"),
    [
        pytest.param({}, STATE_UNAVAILABLE, id="missing"),
        pytest.param(
            {"Shutter/ShutterLevel": "not an option"}, STATE_UNKNOWN, id="not_an_option"
        ),
    ],
)
async def test_state_without_a_usable_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    extra: dict[str, str],
    state: str,
) -> None:
    """Test a value not one of the options is unknown, and one not reported unavailable."""
    values = mock_image_settings.get_image_values.return_value
    mock_image_settings.get_image_values.return_value = {
        path: value for path, value in values.items() if path != "Shutter/ShutterLevel"
    } | extra

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SHUTTER).state == state


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_value_in_another_case_is_still_the_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the camera may report a value in another case than it lists it in."""
    mock_image_settings.get_image_values.return_value = {
        **mock_image_settings.get_image_values.return_value,
        "IrcutFilter/IrcutFilterType": "NIGHT",
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(DAY_NIGHT).state == "night"


@pytest.mark.usefixtures("mock_hikcamera")
async def test_settings_that_cannot_be_selected_get_no_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test which reported settings do not become selects."""
    _use_settings(
        mock_image_settings,
        [
            # Only one choice: nothing to select.
            ImageSetting(
                "Exposure/ExposureType",
                ImageSettingType.SELECT,
                options=["manual"],
                value="manual",
            ),
            # Not a setting the integration knows about.
            ImageSetting(
                "Foo/barMode", ImageSettingType.SELECT, options=["a", "b"], value="a"
            ),
            # Two values that would become the same option.
            ImageSetting(
                "Scene/mode",
                ImageSettingType.SELECT,
                options=["Auto", "auto"],
                value="auto",
            ),
            # Reported as a range, not as choices.
            ImageSetting(
                "Gain/GainLevel",
                ImageSettingType.NUMBER,
                min_value=0,
                max_value=9,
                value="1",
            ),
        ],
        {},
    )

    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert "Skipping Scene/mode" in caplog.text


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("result", "message"),
    [
        (ImageWriteResult(False, 403, "lowPrivilege"), "not allowed to change"),
        (ImageWriteResult(False, 0, "pathNotFound"), "did not accept"),
    ],
)
async def test_write_rejected_by_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    result: ImageWriteResult,
    message: str,
) -> None:
    """Test a rejected write is reported and leaves the state unchanged."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_image_setting.return_value = result

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: SHUTTER, ATTR_OPTION: "1/500"},
            blocking=True,
        )

    assert hass.states.get(SHUTTER).state == "1/1000"


@pytest.mark.usefixtures("mock_hikcamera")
async def test_linked_write_fails_to_reach_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test an error while writing a linked mode is reported."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_image_linked_setting.side_effect = ISAPIError(
        "camera is gone"
    )

    with pytest.raises(HomeAssistantError, match="did not accept the image setting"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: BLC_MODE, ATTR_OPTION: "up"},
            blocking=True,
        )


@pytest.mark.parametrize(
    "cancel", [lambda task: None, asyncio.Task.cancel], ids=["finished", "cancelled"]
)
@pytest.mark.parametrize(
    ("option", "mode", "enabled"), [("CLOSE", "CLOSE", "false"), ("UP", "UP", "true")]
)
@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_linked_write_shows_the_mode_and_its_flag(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    cancel: Callable[[asyncio.Task[None]], object],
    option: str,
    mode: str,
    enabled: str,
) -> None:
    """Test a linked write stores both the mode and its flag, before any poll.

    Also when the action was cancelled while the write ran: the camera made both
    changes anyway.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    (setting,) = (s for s in coordinator.settings if s.path == "BLC/BLCMode")
    started = threading.Event()
    finish = threading.Event()

    def _slow_write(setting: ImageSetting, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        return ImageWriteResult(True, 200, "ok")

    mock_image_settings.set_image_linked_setting = _slow_write
    with patch.object(coordinator, "async_request_refresh", AsyncMock()):
        write = hass.async_create_task(
            coordinator.async_set_linked_setting(setting, option)
        )
        await hass.async_add_executor_job(started.wait, 5)
        cancel(write)
        finish.set()
        await asyncio.wait([write])
        await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["BLC/BLCMode"] == mode
    assert coordinator.data["BLC/enabled"] == enabled


@pytest.mark.parametrize(
    ("path", "linked_enabled_path", "option", "key"),
    [
        # Turning highlight compensation on through its mode.
        ("HLC/HLCMode", "HLC/enabled", "open", "image_setting_conflict_wdr"),
        # Turning it off: the mode and its flag both say off.
        ("HLC/HLCMode", "HLC/enabled", "close", "image_setting_refused"),
        # Backlight compensation is not part of that conflict.
        ("BLC/BLCMode", "BLC/enabled", "open", "image_setting_refused"),
    ],
)
@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_conflict_on_a_linked_write_is_explained_only_when_it_fits(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    path: str,
    linked_enabled_path: str,
    option: str,
    key: str,
) -> None:
    """Test the conflict message of a linked write depends on what it writes."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    setting = ImageSetting(
        path,
        ImageSettingType.SELECT,
        options=["close", "open"],
        linked_enabled_path=linked_enabled_path,
        off_value="close",
    )
    mock_image_settings.set_image_linked_setting.return_value = ImageWriteResult(
        False, 403, "WDROrDehazeMutexHLC"
    )

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_linked_setting(setting, option)

    assert err.value.translation_key == key


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_flag_spelled_otherwise_still_turns_the_mode_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test the values may spell the mode and its flag otherwise than the settings.

    A flag that was missed would leave the mode showing as on.
    """
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(BLC_MODE).state == "auto"
    values = {
        key: value
        for key, value in image_values.items()
        if key not in ("BLC/BLCMode", "BLC/enabled")
    }

    mock_image_settings.get_image_values.return_value = {
        **values,
        "blc/ENABLED": "false",
    }
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(BLC_MODE).state == "close"

    mock_image_settings.get_image_values.return_value = {
        **values,
        "blc/enabled": "true",
        "blc/blcmode": "AUTO",
    }
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(BLC_MODE).state == "auto"


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("path", "camera_options"),
    [
        ("Shutter/ShutterLevel", ["1/30", "1/30"]),
        # The value is read in any case: "F1.6" could be either.
        ("Iris/IrisLevel", ["F1.6", "f1.6"]),
    ],
)
async def test_a_list_with_a_value_twice_gets_no_select(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
    path: str,
    camera_options: list[str],
) -> None:
    """Test options shown as the camera sends them are checked for repeats too.

    pyHik keeps a value the camera lists twice: the select would have one option
    fewer than the camera's list, and the setting would not have two choices. Two
    values that only differ in case cannot be told apart in what the camera
    reports.
    """
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            path,
            ImageSettingType.SELECT,
            options=camera_options,
            value=camera_options[0],
        ),
    ]
    mock_image_settings.get_image_values.return_value = {path: camera_options[0]}

    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
