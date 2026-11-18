"""Test Hikvision image setting selects."""

from unittest.mock import MagicMock

from pyhik.image import ImageSetting, ImageSettingType, ImageWriteResult
from pyhik.isapi import ISAPIError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

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


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("values", "expected"),
    [
        # The camera does not say whether the feature is on, so the mode is shown.
        ({"HLC/HLCMode": "auto"}, "auto"),
        # Nothing is known, which is not the same as off.
        ({}, STATE_UNKNOWN),
        ({"HLC/enabled": "false"}, "close"),
    ],
)
async def test_linked_mode_without_an_enabled_flag(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    values: dict[str, str],
    expected: str,
) -> None:
    """Test a missing enabled flag is not read as off."""
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
    "extra",
    [
        pytest.param({}, id="missing"),
        pytest.param({"Shutter/ShutterLevel": "not an option"}, id="not_an_option"),
    ],
)
async def test_state_unknown_without_a_usable_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    extra: dict[str, str],
) -> None:
    """Test a value that is missing or not one of the options is unknown."""
    values = mock_image_settings.get_image_values.return_value
    mock_image_settings.get_image_values.return_value = {
        path: value for path, value in values.items() if path != "Shutter/ShutterLevel"
    } | extra

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SHUTTER).state == STATE_UNKNOWN


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
