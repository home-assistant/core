"""Calendar data source."""

import dataclasses
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_TYPE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN, CalendarEntity, event_dict_factory

DATA_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): vol.In("get_events"),
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("start"): cv.datetime,
        vol.Required("end"): cv.datetime,
    }
)


async def async_get_data(hass: HomeAssistant, config: ConfigType) -> Any:
    """Provide the data for the specified data source configuration."""
    component: EntityComponent[CalendarEntity] = hass.data[DOMAIN]
    entity_id = config[CONF_ENTITY_ID]
    if not (entity := component.get_entity(entity_id)):
        raise vol.Invalid(f"Entity '{entity_id}' not found")
    events = await entity.async_get_events(hass, config["start"], config["end"])
    return [
        dataclasses.asdict(event, dict_factory=event_dict_factory) for event in events
    ]
