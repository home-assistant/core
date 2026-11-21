"""Test Hikvision image setting numbers."""

import math
from unittest.mock import MagicMock

from pyhik.image import (
    ImageSetting,
    ImageSettingType,
    ImageWriteResult,
    parse_image_capabilities,
    parse_image_values,
)
from pyhik.isapi import ISAPIError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import image_channel_with, setup_integration
from .conftest import TEST_DEVICE_ID

BRIGHTNESS = "number.front_camera_brightness"
WDR_LEVEL = "number.front_camera_wdr_level"
SMART_LIGHT_DISTANCE = "number.front_camera_smart_supplement_light_distance"
WHITE_BALANCE_RED = "number.front_camera_white_balance_red"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load during test."""
    return [Platform.NUMBER]


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_hikcamera", "mock_image_settings"
)
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all number entities of a camera."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_enabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only the commonly used numbers are enabled by default."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(BRIGHTNESS).state == "80.0"
    assert hass.states.get(WHITE_BALANCE_RED) is None
    assert (
        entity_registry.async_get(WHITE_BALANCE_RED).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_hikcamera", "mock_image_settings"
)
async def test_range_comes_from_the_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that each number uses the range the camera reports."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(WDR_LEVEL).attributes[ATTR_MIN] == 0
    assert hass.states.get(WDR_LEVEL).attributes[ATTR_MAX] == 100
    assert hass.states.get(SMART_LIGHT_DISTANCE).attributes[ATTR_MIN] == 1
    assert hass.states.get(SMART_LIGHT_DISTANCE).attributes[ATTR_MAX] == 100


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("key", "path", "unit"),
    [
        ("gain_limit", "Gain/GainLimit", None),
        ("auto_iris_level", "Exposure/autoIrisLevel", None),
        ("p_iris_level", "Exposure/pIris/IrisLevel", None),
        ("max_iris_level", "Iris/maxIrisLevelLimit", None),
        ("min_iris_level", "Iris/minIrisLevelLimit", None),
        ("smart_noise_reduction_level", "smartNoiseReduce/level", None),
        ("defog_level", "Dehaze/DehazeLevel", None),
        (
            "smart_supplement_light_high_light_distance",
            "Exposure/OverexposeSuppress/hightLightDistanceLevel",
            None,
        ),
        (
            "smart_supplement_light_low_light_distance",
            "Exposure/OverexposeSuppress/lowLightDistanceLevel",
            None,
        ),
        (
            "white_light_brightness_limit",
            "SupplementLight/whiteLightbrightnessLimit",
            PERCENTAGE,
        ),
        ("ir_light_brightness", "SupplementLight/irLightBrightness", PERCENTAGE),
        (
            "ir_light_brightness_limit",
            "SupplementLight/irLightbrightnessLimit",
            PERCENTAGE,
        ),
        ("ir_high_brightness", "SupplementLight/highIrLightBrightness", PERCENTAGE),
        ("ir_low_brightness", "SupplementLight/lowIrLightBrightness", PERCENTAGE),
        ("ir_brightness_limit", "IrLight/brightnessLimit", PERCENTAGE),
        (
            "event_intelligence_white_light_brightness",
            "SupplementLight/EventIntelligenceModeCfg/whiteLightBrightness",
            PERCENTAGE,
        ),
        (
            "event_intelligence_ir_light_brightness",
            "SupplementLight/EventIntelligenceModeCfg/irLightBrightness",
            PERCENTAGE,
        ),
        (
            "lens_distortion_correction_level",
            "LensDistortionCorrection/accurateLevel",
            None,
        ),
    ],
)
async def test_numbers_the_fixture_camera_does_not_have(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
    key: str,
    path: str,
    unit: str | None,
) -> None:
    """Test each number is found from the capabilities, and writes its own path.

    They are disabled by default, as configuration entities, and their range is
    the camera's.
    """
    capabilities = image_channel_with(path, ' min="1" max="80">40')
    values = image_channel_with(path, ">30")
    mock_image_settings.get_image_settings.return_value = parse_image_capabilities(
        capabilities, values
    )
    mock_image_settings.get_image_values.return_value = parse_image_values(values)

    await setup_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        NUMBER_DOMAIN, DOMAIN, f"{TEST_DEVICE_ID}_image_{key}"
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry.translation_key == key
    assert entry.entity_category is EntityCategory.CONFIG
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ) == [entry]

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(entity_id)
    assert float(state.state) == 30
    assert state.attributes[ATTR_MIN] == 1
    assert state.attributes[ATTR_MAX] == 80
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 55},
        blocking=True,
    )
    mock_image_settings.set_image_setting.assert_called_once_with(path, "55")


@pytest.mark.usefixtures("mock_hikcamera")
async def test_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test changing a number writes a whole number to the camera."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.get_image_values.return_value = {
        **mock_image_settings.get_image_values.return_value,
        "Color/brightnessLevel": "90",
    }

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: BRIGHTNESS, ATTR_VALUE: 90.0},
        blocking=True,
    )

    mock_image_settings.set_image_setting.assert_called_once_with(
        "Color/brightnessLevel", "90"
    )
    assert hass.states.get(BRIGHTNESS).state == "90.0"


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    "value",
    [
        90.9,
        90.001,
        90.00000001,
        # Not converted, so no round-off to absorb: refused however small.
        90.00000000001,
        "nan",
    ],
)
async def test_a_value_that_is_not_whole_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    value: float | str,
) -> None:
    """Test a fraction, even a small one, or NaN is not cut off, but refused.

    The action turns "nan" into a float that passes the range check. Nothing is
    written.
    """
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match="whole numbers"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: BRIGHTNESS, ATTR_VALUE: value},
            blocking=True,
        )

    mock_image_settings.set_image_setting.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_write_rejected_by_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a rejected write is reported and leaves the state unchanged."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, "lowPrivilege"
    )

    with pytest.raises(HomeAssistantError, match="not allowed to change"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: BRIGHTNESS, ATTR_VALUE: 90},
            blocking=True,
        )

    assert hass.states.get(BRIGHTNESS).state == "80.0"


@pytest.mark.usefixtures("mock_hikcamera")
async def test_write_fails_to_reach_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test an error while writing is reported."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_image_setting.side_effect = ISAPIError("camera is gone")

    with pytest.raises(HomeAssistantError, match="did not accept the image setting"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: BRIGHTNESS, ATTR_VALUE: 90},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    "extra",
    [
        pytest.param({}, id="missing"),
        pytest.param({"Color/brightnessLevel": "not a number"}, id="not_a_number"),
    ],
)
async def test_state_unknown_without_a_usable_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    extra: dict[str, str],
) -> None:
    """Test a value that is missing or not a number gives an unknown state."""
    values = mock_image_settings.get_image_values.return_value
    mock_image_settings.get_image_values.return_value = {
        path: value for path, value in values.items() if path != "Color/brightnessLevel"
    } | extra

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(BRIGHTNESS).state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_hikcamera")
async def test_only_numeric_known_settings_get_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test which reported settings become numbers."""
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = None
    client.get_image_settings.return_value = [
        # Some firmware reports the shutter as a range, others as a list of choices.
        ImageSetting(
            "Shutter/ShutterLevel",
            ImageSettingType.NUMBER,
            min_value=0,
            max_value=9,
            value="3",
        ),
        # A choice, not a number.
        ImageSetting(
            "IrcutFilter/nightToDayFilterLevel",
            ImageSettingType.SELECT,
            options=["1", "2"],
            value="1",
        ),
        # Not a setting the integration knows about.
        ImageSetting(
            "Foo/barLevel", ImageSettingType.NUMBER, min_value=0, max_value=9, value="1"
        ),
        # A number the camera gives no range for has no slider to show.
        ImageSetting(
            "Color/contrastLevel", ImageSettingType.NUMBER, min_value=0, value="50"
        ),
        ImageSetting(
            "Color/saturationLevel", ImageSettingType.NUMBER, max_value=100, value="50"
        ),
        ImageSetting(
            "SupplementLight/whiteLightBrightness",
            ImageSettingType.NUMBER,
            min_value=0,
            max_value=100,
            value="30",
        ),
        # A known path in different capitalization is still matched.
        ImageSetting(
            "exposure/overexposesuppress/hightlightdistancelevel",
            ImageSettingType.NUMBER,
            min_value=0,
            max_value=100,
            value="30",
        ),
    ]
    client.get_image_values.return_value = {
        "Shutter/ShutterLevel": "3",
        "SupplementLight/whiteLightBrightness": "30",
    }

    await setup_integration(hass, mock_config_entry)

    unique_ids = {
        entry.unique_id.split("_image_", 1)[1]
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    # The keys of the descriptions, whatever the firmware's spelling of the path.
    assert unique_ids == {
        "shutter_speed",
        "light_brightness",
        "smart_supplement_light_high_light_distance",
    }


@pytest.mark.usefixtures("mock_hikcamera")
async def test_supplement_light_brightness_is_a_percentage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test the brightness of a supplement light is shown as a share of its power.

    The level of the image's brightness has no unit: it is not a share of anything.
    """
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = None
    client.get_image_settings.return_value = [
        ImageSetting(
            "SupplementLight/whiteLightBrightness",
            ImageSettingType.NUMBER,
            min_value=0,
            max_value=100,
            value="30",
        ),
        ImageSetting(
            "Color/brightnessLevel",
            ImageSettingType.NUMBER,
            min_value=0,
            max_value=100,
            value="50",
        ),
    ]
    client.get_image_values.return_value = {
        "SupplementLight/whiteLightBrightness": "30",
        "Color/brightnessLevel": "50",
    }

    await setup_integration(hass, mock_config_entry)

    light = hass.states.get("number.front_camera_light_brightness")
    assert light is not None
    assert light.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert ATTR_UNIT_OF_MEASUREMENT not in hass.states.get(BRIGHTNESS).attributes


@pytest.mark.usefixtures("mock_hikcamera")
async def _async_set_up_delay_in_minutes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> str:
    """Set up the night-to-day delay, shown in minutes; return its entity ID."""
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = None
    client.get_image_settings.return_value = [
        ImageSetting(
            "IrcutFilter/nightToDayFilterTime",
            ImageSettingType.NUMBER,
            min_value=0,
            max_value=120,
            value="30",
        ),
    ]
    client.get_image_values.return_value = {"IrcutFilter/nightToDayFilterTime": "30"}
    await setup_integration(hass, mock_config_entry)
    (entry,) = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    entity_registry.async_update_entity(entry.entity_id, disabled_by=None)
    entity_registry.async_update_entity_options(
        entry.entity_id, NUMBER_DOMAIN, {"unit_of_measurement": UnitOfTime.MINUTES}
    )
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        hass.states.get(entry.entity_id).attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfTime.MINUTES
    )
    return entry.entity_id


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_duration_set_in_another_unit_is_written_whole(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the round-off of a unit conversion does not refuse a whole value.

    31 s set as 0.5166... min comes back as 31.000000000000004 s.
    """
    entity_id = await _async_set_up_delay_in_minutes(
        hass, mock_config_entry, mock_isapi_client, entity_registry
    )

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 31 / 60},
        blocking=True,
    )

    mock_isapi_client.return_value.set_image_setting.assert_called_once_with(
        "IrcutFilter/nightToDayFilterTime", "31"
    )


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_fractional_duration_set_in_another_unit_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a real fraction after the conversion is refused, not rounded.

    0.52 min is 31.2 s: more than the round-off of a conversion.
    """
    entity_id = await _async_set_up_delay_in_minutes(
        hass, mock_config_entry, mock_isapi_client, entity_registry
    )

    with pytest.raises(ServiceValidationError, match="whole numbers"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 0.52},
            blocking=True,
        )

    mock_isapi_client.return_value.set_image_setting.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
async def test_a_value_that_is_not_a_number_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    value: str,
) -> None:
    """Test a reported value that parses, but is no number to show, is unknown."""
    mock_image_settings.get_image_values.return_value = {
        **mock_image_settings.get_image_values.return_value,
        "Color/brightnessLevel": value,
    }
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(BRIGHTNESS).state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_range_a_slider_cannot_use_gets_no_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a setting whose range is not numbers, or the wrong way around, is left out.

    Every value would be refused.
    """
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = None
    client.get_image_settings.return_value = [
        ImageSetting(
            "Color/brightnessLevel",
            ImageSettingType.NUMBER,
            min_value=math.nan,
            max_value=100,
            value="50",
        ),
        ImageSetting(
            "Color/contrastLevel",
            ImageSettingType.NUMBER,
            min_value=0,
            max_value=math.inf,
            value="50",
        ),
        ImageSetting(
            "Color/saturationLevel",
            ImageSettingType.NUMBER,
            min_value=100,
            max_value=0,
            value="50",
        ),
        # A single value is a range too.
        ImageSetting(
            "Sharpness/SharpnessLevel",
            ImageSettingType.NUMBER,
            min_value=50,
            max_value=50,
            value="50",
        ),
    ]
    client.get_image_values.return_value = {
        "Color/brightnessLevel": "50",
        "Color/contrastLevel": "50",
        "Color/saturationLevel": "50",
        "Sharpness/SharpnessLevel": "50",
    }

    await setup_integration(hass, mock_config_entry)

    assert {
        entry.unique_id.split("_image_", 1)[1]
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    } == {"sharpness"}
