"""Config flow to configure proximity component."""
# mypy: allow-untyped-defs, no-check-untyped-defs
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICES, CONF_UNIT_OF_MEASUREMENT, CONF_ZONE
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    DEFAULT_PROXIMITY_ZONE,
    DEFAULT_TOLERANCE,
    UNITS,
)
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class ProximityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Proximity configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        entities_reg = await self.hass.helpers.entity_registry.async_get_registry()
        entities = list(entities_reg.entities.keys())
        zones_list = [
            entity.original_name
            for entity in entities_reg.entities.values()
            if entity.domain == "zone"
        ]
        zones = ["home"] + zones_list

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_ZONE, default=[DEFAULT_PROXIMITY_ZONE]): vol.All(
                    cv.string, vol.In(zones)
                ),
                vol.Required(CONF_DEVICES): cv.multi_select(entities),
                vol.Optional(CONF_IGNORED_ZONES, default=[]): cv.multi_select(zones),
                vol.Optional(
                    CONF_TOLERANCE, default=DEFAULT_TOLERANCE
                ): cv.positive_int,
                vol.Optional(CONF_UNIT_OF_MEASUREMENT): vol.All(
                    cv.string, vol.In(UNITS)
                ),
            },
            extra=vol.REMOVE_EXTRA,
        )

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ZONE])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_ZONE], data=user_input)
        return self.async_show_form(step_id="user", data_schema=data_schema)
