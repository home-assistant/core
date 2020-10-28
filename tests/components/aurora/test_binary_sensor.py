"""The tests for the Aurora sensor platform."""
import re

from homeassistant.components.aurora import binary_sensor as aurora

from tests.common import load_fixture


def test_setup_and_initial_state(hass, requests_mock):
    """Test that the component is created and initialized as expected."""
    uri = re.compile(r"http://services\.swpc\.noaa\.gov/text/aurora-nowcast-map\.txt")
    requests_mock.get(uri, text=load_fixture("aurora.txt"))

    entities = []

    def mock_add_entities(new_entities, update_before_add=False):
        """Mock add entities."""
        if update_before_add:
            for entity in new_entities:
                entity.update()

        for entity in new_entities:
            entities.append(entity)

    config = {"name": "Test", "forecast_threshold": 75}
    aurora.setup_platform(hass, config, mock_add_entities)

    aurora_component = entities[0]
    assert len(entities) == 1
    assert aurora_component.name == "Test"
    assert aurora_component.device_state_attributes["visibility_level"] == "0"
    assert aurora_component.device_state_attributes["message"] == "nothing's out"
    assert not aurora_component.is_on


def test_custom_threshold_works(hass, requests_mock):
    """Test that the config can take a custom forecast threshold."""
    uri = re.compile(r"http://services\.swpc\.noaa\.gov/text/aurora-nowcast-map\.txt")
    requests_mock.get(uri, text=load_fixture("aurora.txt"))

    entities = []

    def mock_add_entities(new_entities, update_before_add=False):
        """Mock add entities."""
        if update_before_add:
            for entity in new_entities:
                entity.update()

        for entity in new_entities:
            entities.append(entity)

    config = {"name": "Test", "forecast_threshold": 1}
    hass.config.longitude = 18.987
    hass.config.latitude = 69.648

    aurora.setup_platform(hass, config, mock_add_entities)

    aurora_component = entities[0]
    assert aurora_component.aurora_data.visibility_level == "16"
    assert aurora_component.is_on
