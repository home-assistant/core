"""Test Hikvision image setting sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyhik.image import (
    ImageSetting,
    ImageSettingType,
    parse_image_capabilities,
    parse_image_values,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.components.hikvision.coordinator import SCAN_INTERVAL
from homeassistant.components.hikvision.sensor import SENSOR_DESCRIPTIONS
from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from . import image_channel_with, setup_integration
from .conftest import TEST_DEVICE_ID

EXPOSURE_MODE = "sensor.front_camera_exposure_mode"

# How some firmware spells "true".
FIRMWARE_TRUE = "ture"  # codespell:ignore ture


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load during test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_hikcamera", "mock_image_settings"
)
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor entities of a camera."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensors are diagnostic and disabled by default."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(EXPOSURE_MODE) is None
    entry = entity_registry.async_get(EXPOSURE_MODE)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hikcamera")
async def test_only_single_choice_settings_get_a_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test settings with several choices are left to the selects."""
    await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    keys = {
        description.path.lower(): description.key for description in SENSOR_DESCRIPTIONS
    }
    sensors = {
        keys[setting.path.lower()]
        for setting in mock_image_settings.get_image_settings.return_value
        if setting.type is ImageSettingType.SELECT
        and len(setting.options) == 1
        and setting.path.lower() in keys
    }
    assert sensors
    assert {entity.unique_id.split("_image_", 1)[1] for entity in entities} == sensors
    assert hass.states.get(EXPOSURE_MODE).state == "manual"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hikcamera")
@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        ({"Exposure/ExposureType": "auto"}, STATE_UNKNOWN),
        # The camera may report the value in another case than it lists it in.
        ({"Exposure/ExposureType": "MANUAL"}, "manual"),
        # Missing from the values the camera sends: it does not have it now.
        ({}, STATE_UNAVAILABLE),
    ],
)
async def test_value_follows_the_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    reported: dict[str, str],
    expected: str,
) -> None:
    """Test the sensor shows the value the next scheduled poll reads.

    A value that is not the setting's choice is unknown: an enum sensor only
    shows one of its options.
    """
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(EXPOSURE_MODE).state == "manual"
    values = {
        path: value
        for path, value in mock_image_settings.get_image_values.return_value.items()
        if path != "Exposure/ExposureType"
    }
    mock_image_settings.get_image_values.return_value = {**values, **reported}
    polls = mock_image_settings.get_image_values.call_count

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_image_settings.get_image_values.call_count == polls + 1
    assert hass.states.get(EXPOSURE_MODE).state == expected


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hikcamera")
async def test_path_is_matched_in_any_case(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a camera that spells a path differently still gets its sensor."""
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            "exposure/exposureType",
            ImageSettingType.SELECT,
            options=["manual"],
            value="manual",
        )
    ]
    mock_image_settings.get_image_values.return_value = {
        "exposure/exposureType": "manual"
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(EXPOSURE_MODE).state == "manual"


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("key", "path", "value", "shown"),
    [
        # Settings real cameras offer with one choice only.
        ("supplement_light_mode", "SupplementLight/mode", "auto", "auto"),
        ("ir_light_mode", "IrLight/mode", "auto", "auto"),
        (
            "focus_distance_mode",
            "FocusConfiguration/focusDistanceMode",
            "compatible",
            "compatible",
        ),
        ("capture_mode", "CaptureMode/mode", "1920*1080@30fps", "1920_1080_30fps"),
        # The flag of backlight compensation, offered as on only, in either
        # spelling: see FIRMWARE_TRUE.
        ("backlight_compensation", "BLC/enabled", "true", "true"),
        ("backlight_compensation", "BLC/enabled", FIRMWARE_TRUE, FIRMWARE_TRUE),
        # A flag that is otherwise a switch, offered with one value only.
        ("highlight_compensation", "HLC/enabled", "true", "true"),
        ("image_flip", "ImageFlip/enabled", "false", "false"),
        # Shown as the camera reports it.
        ("iris_level", "Iris/IrisLevel", "F1.6", "F1.6"),
    ],
)
async def test_single_choice_settings_the_fixture_camera_does_not_have(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
    key: str,
    path: str,
    value: str,
    shown: str,
) -> None:
    """Test a setting with one choice is a sensor showing it as the select would."""
    capabilities = image_channel_with(path, f' opt="{value}">{value}')
    values = image_channel_with(path, f">{value}")
    mock_image_settings.get_image_settings.return_value = parse_image_capabilities(
        capabilities, values
    )
    mock_image_settings.get_image_values.return_value = parse_image_values(values)

    await setup_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{TEST_DEVICE_ID}_image_{key}"
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry.translation_key == key
    assert entry.entity_category is EntityCategory.DIAGNOSTIC
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ) == [entry]

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(entity_id)
    assert state.state == shown
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == [shown]


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_single_choice_setting_without_a_description_gets_no_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a setting the integration does not know is not shown, the others are."""
    settings = []
    values: dict[str, str] = {}
    for path, value in (("Unknown/mode", "auto"), ("Iris/IrisLevel", "F1.6")):
        document = image_channel_with(path, f">{value}")
        settings += parse_image_capabilities(
            image_channel_with(path, f' opt="{value}">{value}'), document
        )
        values |= parse_image_values(document)
    mock_image_settings.get_image_settings.return_value = settings
    mock_image_settings.get_image_values.return_value = values

    await setup_integration(hass, mock_config_entry)

    assert [
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    ] == [f"{TEST_DEVICE_ID}_image_iris_level"]


@pytest.mark.parametrize(
    ("key", "option"),
    [
        ("supplement_light_mode", "auto"),
        ("ir_light_mode", "auto"),
        ("focus_distance_mode", "compatible"),
        ("capture_mode", "1920_1080_30fps"),
        ("backlight_compensation", "true"),
        ("backlight_compensation", FIRMWARE_TRUE),
        ("highlight_compensation", "true"),
        ("image_flip", "false"),
    ],
)
async def test_single_choice_sensor_options_have_a_name(
    hass: HomeAssistant, key: str, option: str
) -> None:
    """Test a translated option of a single-choice sensor has its own state name."""
    translations = await async_get_translations(hass, "en", "entity", [DOMAIN])
    assert f"component.{DOMAIN}.entity.sensor.{key}.state.{option}" in translations


@pytest.mark.usefixtures("mock_hikcamera")
async def test_no_sensors_without_image_settings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a camera without image settings gets no sensors."""
    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_every_option_of_a_select_has_a_sensor_name(hass: HomeAssistant) -> None:
    """Test a sensor can name any option the select can.

    A camera that offers only one of them gets a sensor instead of the select.
    """
    translations = await async_get_translations(hass, "en", "entity", [DOMAIN])
    select = f"component.{DOMAIN}.entity.select."
    sensor = f"component.{DOMAIN}.entity.sensor."
    assert [
        key
        for key in translations
        if key.startswith(select)
        and ".state." in key
        and sensor + key.removeprefix(select) not in translations
    ] == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hikcamera")
async def test_the_option_is_shown_as_the_select_shows_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the sensor shows the translated option, not the camera's own spelling.

    Values such as shutter speeds are shown as the camera reports them.
    """
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            "IrcutFilter/IrcutFilterType",
            ImageSettingType.SELECT,
            options=["eventTrigger"],
            value="eventTrigger",
        ),
        ImageSetting(
            "Shutter/ShutterLevel",
            ImageSettingType.SELECT,
            options=["1/25"],
            value="1/25",
        ),
    ]
    mock_image_settings.get_image_values.return_value = {
        "IrcutFilter/IrcutFilterType": "eventTrigger",
        "Shutter/ShutterLevel": "1/25",
    }

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.front_camera_day_night_mode")
    assert state.state == "eventtrigger"
    assert state.attributes["options"] == ["eventtrigger"]
    assert hass.states.get("sensor.front_camera_shutter_speed").state == "1/25"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hikcamera")
@pytest.mark.parametrize(
    ("enabled", "expected"),
    [
        # Off: the off option, though the mode is missing from the values.
        ("false", "close"),
        # On: the mode is missing, so there is nothing to show.
        ("true", STATE_UNKNOWN),
        # Neither true nor false says nothing: not off.
        ("1", STATE_UNKNOWN),
    ],
)
async def test_a_linked_mode_shows_off_while_its_feature_is_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    enabled: str,
    expected: str,
) -> None:
    """Test a single-choice linked mode follows its flag, as the select does.

    The mode is missing from the values while the feature is off.
    """
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            "BLC/BLCMode",
            ImageSettingType.SELECT,
            options=["CLOSE"],
            value="CLOSE",
            linked_enabled_path="BLC/enabled",
            off_value="CLOSE",
        ),
    ]
    mock_image_settings.get_image_values.return_value = {"BLC/enabled": enabled}

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.front_camera_backlight_compensation_mode")
    assert state.state == expected
