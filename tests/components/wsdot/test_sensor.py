"""The tests for the WSDOT platform."""

from datetime import datetime, timedelta, timezone
import re

import requests_mock

from homeassistant.components.wsdot import sensor as wsdot_sensor
from homeassistant.components.wsdot.const import (
    ATTR_DESCRIPTION,
    ATTR_TIME_UPDATED,
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_TRAVEL_TIMES,
    RESOURCE,
    SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


async def test_setup_with_config(hass: HomeAssistant, mock_config_data: dict) -> None:
    """Test the platform setup with configuration."""
    assert await async_setup_component(hass, "sensor", {"wsdot": {"data": mock_config_data}})


async def test_setup(hass: HomeAssistant, mock_config_entry:MockConfigEntry, requests_mock: requests_mock.Mocker) -> None:
    """Test for operational WSDOT sensor with proper attributes."""
    entities = []

    def add_entities(new_entities):
        """Mock add entities."""
        for entity in new_entities:
            entity.hass = hass
            entity.update()

        entities.extend(new_entities)

    uri = re.compile(RESOURCE + "*")
    requests_mock.get(uri, text=load_fixture("wsdot/wsdot.json"))
    await wsdot_sensor.async_setup_entry(hass, mock_config_entry, add_entities)
    assert len(entities) == 1
    sensor = entities[0]
    assert sensor.name == "I90 EB"
    assert sensor.state == 11
    assert (
        sensor.extra_state_attributes[ATTR_DESCRIPTION]
        == "Downtown Seattle to Downtown Bellevue via I-90"
    )
    assert sensor.extra_state_attributes[ATTR_TIME_UPDATED] == datetime(
        2017, 1, 21, 15, 10, tzinfo=timezone(timedelta(hours=-8))
    )
