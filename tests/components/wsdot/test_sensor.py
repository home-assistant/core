"""The tests for the WSDOT platform."""

from datetime import datetime, timedelta, timezone
import re

import requests_mock

from homeassistant.components.wsdot import sensor as wsdot
from homeassistant.components.wsdot.sensor import (
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

from tests.common import load_fixture

config = {
    CONF_API_KEY: "foo",
    SCAN_INTERVAL: timedelta(seconds=120),
    CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I90 EB"}],
}


async def test_setup_with_config(hass: HomeAssistant) -> None:
    """Test the platform setup with configuration."""
    assert await async_setup_component(hass, "sensor", {"wsdot": config})


async def test_setup(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test for operational WSDOT sensor with proper attributes."""
    entities = []

    def add_entities(new_entities, update_before_add=False):
        """Mock add entities."""
        for entity in new_entities:
            entity.hass = hass

        if update_before_add:
            for entity in new_entities:
                entity.update()

        entities.extend(new_entities)

    uri = re.compile(RESOURCE + "*")
    requests_mock.get(uri, text=load_fixture("wsdot/wsdot.json"))
    wsdot.setup_platform(hass, config, add_entities)
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
