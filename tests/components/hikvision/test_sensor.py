"""Test Hikvision image setting sensors."""

from unittest.mock import MagicMock

from pyhik.image import ImageSetting, ImageSettingType
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

EXPOSURE_MODE = "sensor.front_camera_exposure_mode"


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
    sensors = {
        setting.path.lower()
        for setting in mock_image_settings.get_image_settings.return_value
        if setting.type is ImageSettingType.SELECT and len(setting.options) == 1
    }
    assert sensors
    assert {entity.unique_id.split("_image_", 1)[1].lower() for entity in entities} <= (
        sensors
    )
    assert hass.states.get(EXPOSURE_MODE).state == "manual"


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_hikcamera", "mock_image_settings"
)
async def test_value_follows_the_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor shows the value the coordinator last read."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinator

    coordinator.async_set_updated_data(
        {**coordinator.data, "Exposure/ExposureType": "auto"}
    )
    await hass.async_block_till_done()

    assert hass.states.get(EXPOSURE_MODE).state == "auto"


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
