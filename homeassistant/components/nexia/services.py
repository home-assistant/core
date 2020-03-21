"""Services for nexia."""

import voluptuous as vol

from homeassistant.components.climate.const import ATTR_HUMIDITY
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv

from .const import ATTR_AIRCLEANER_MODE, CLIMATE_ZONE_ENTITIES, DOMAIN

SERVICE_SET_AIRCLEANER_MODE = "set_aircleaner_mode"
SERVICE_SET_HUMIDIFY_SETPOINT = "set_humidify_setpoint"

SET_FAN_MIN_ON_TIME_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_AIRCLEANER_MODE): cv.string,
    }
)

SET_HUMIDITY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_HUMIDITY): vol.All(
            vol.Coerce(int), vol.Range(min=35, max=65)
        ),
    }
)


def register_climate_services(hass):
    """Register all climate services for nexia."""

    def _apply_thermostat_service(entity_ids, thermostat_func, thermostat_value):
        """Handle services to apply."""
        seen_thermostats = set()
        target_entities = []
        # If they do not specify an entity_id we apply the setting
        # to all nexia thermostats across all config entries.

        for config_entry_id in hass.data[DOMAIN]:
            nexia_data = hass.data[DOMAIN][config_entry_id]
            climate_zone_entities = nexia_data[CLIMATE_ZONE_ENTITIES]

            # Since we do not have thermostat entities, we need
            # to cycle though all the zones to find the thermostat
            # that belongs to each zone.  Since zones can share
            # a thermostat, we only want to target entities
            # that we haven't already seen the thermostat.
            for zone_entity in climate_zone_entities:
                if not entity_ids or zone_entity.entity_id in entity_ids:
                    if zone_entity.thermostat not in seen_thermostats:
                        seen_thermostats.add(zone_entity.thermostat)
                        target_entities.append(zone_entity)

        for entity in target_entities:
            getattr(entity, thermostat_func)(thermostat_value)

    async def _humidify_set_service(service):
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        humidity = service.data.get(ATTR_HUMIDITY)
        await hass.async_add_executor_job(
            _apply_thermostat_service,
            entity_ids,
            "set_humidify_setpoint",
            (int(humidity) / 100.0),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HUMIDIFY_SETPOINT,
        _humidify_set_service,
        schema=SET_HUMIDITY_SCHEMA,
    )

    async def _aircleaner_set_service(service):
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        aircleaner_mode = service.data.get(ATTR_AIRCLEANER_MODE)
        await hass.async_add_executor_job(
            _apply_thermostat_service,
            entity_ids,
            "set_aircleaner_mode",
            aircleaner_mode,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_AIRCLEANER_MODE,
        _aircleaner_set_service,
        schema=SET_FAN_MIN_ON_TIME_SCHEMA,
    )
