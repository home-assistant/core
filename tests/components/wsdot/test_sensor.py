"""The tests for the WSDOT platform."""

from datetime import datetime, timedelta, timezone

from homeassistant.components.wsdot.sensor import (
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_TRAVEL_TIMES,
    async_setup_platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

config = {
    CONF_API_KEY: "foo",
    CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I90 EB"}],
}


async def test_setup_with_config(hass: HomeAssistant) -> None:
    """Test the platform setup with configuration."""
    assert await async_setup_component(hass, "sensor", {"wsdot": config})


async def test_setup(
    hass: HomeAssistant,
    mock_travel_time: None,
) -> None:
    """Test for operational WSDOT sensor with proper attributes."""
    entities = []

    def add_entities(new_entities, update_before_add=False):
        """Mock add entities."""
        for entity in new_entities:
            entity.hass = hass
        entities.extend(new_entities)

    await async_setup_platform(hass, config, add_entities)
    for entity in entities:
        await entity.async_update()

    assert len(entities) == 1
    sensor = entities[0]
    assert sensor.name == "I90 EB"
    assert sensor.state == 11
    assert (
        sensor.extra_state_attributes["Description"]
        == "Downtown Seattle to Downtown Bellevue via I-90"
    )
    assert sensor.extra_state_attributes["TimeUpdated"] == datetime(
        2017, 1, 21, 15, 10, tzinfo=timezone(timedelta(hours=-8))
    )
