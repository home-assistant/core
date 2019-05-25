"""Support to graphs card in the UI."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_ENTITIES, CONF_NAME, ATTR_ENTITY_ID
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'history_graph'

CONF_HOURS_TO_SHOW = 'hours_to_show'
CONF_REFRESH = 'refresh'
ATTR_HOURS_TO_SHOW = CONF_HOURS_TO_SHOW
ATTR_REFRESH = CONF_REFRESH


GRAPH_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITIES): cv.entity_ids,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_HOURS_TO_SHOW, default=24): vol.Range(min=1),
    vol.Optional(CONF_REFRESH, default=0): vol.Range(min=0),
})


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: cv.schema_with_slug_keys(GRAPH_SCHEMA),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Load graph configurations."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass)
    graphs = []

    for object_id, cfg in config[DOMAIN].items():
        name = cfg.get(CONF_NAME, object_id)
        graph = HistoryGraphEntity(name, cfg)
        graphs.append(graph)

    await component.async_add_entities(graphs)

    return True


class HistoryGraphEntity(Entity):
    """Representation of a graph entity."""

    def __init__(self, name, cfg):
        """Initialize the graph."""
        self._name = name
        self._hours = cfg[CONF_HOURS_TO_SHOW]
        self._refresh = cfg[CONF_REFRESH]
        self._entities = cfg[CONF_ENTITIES]

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = {
            ATTR_HOURS_TO_SHOW: self._hours,
            ATTR_REFRESH: self._refresh,
            ATTR_ENTITY_ID: self._entities,
        }
        return attrs
