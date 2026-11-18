"""Test Hikvision image setting numbers."""

from unittest.mock import MagicMock

from pyhik.image import ImageSetting, ImageSettingType, ImageWriteResult
from pyhik.isapi import ISAPIError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

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
async def test_a_value_that_is_not_whole_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a fraction is not cut off, but refused, and nothing is written."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match="whole numbers"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: BRIGHTNESS, ATTR_VALUE: 90.9},
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
    assert unique_ids == {
        "shutter/shutterlevel",
        "supplementlight/whitelightbrightness",
        "exposure/overexposesuppress/hightlightdistancelevel",
    }
