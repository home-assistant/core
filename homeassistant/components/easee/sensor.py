"""Easee charger sensor."""
from datetime import datetime, timedelta
import logging
from typing import Dict

from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity

from .const import (
    CUSTOM_UNITS,
    CUSTOM_UNITS_TABLE,
    DOMAIN,
    EASEE_ENTITIES,
    MEASURED_CONSUMPTION_DAYS,
)
from .entity import ChargerEntity, convert_units_funcs, round_2_dec

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Init the sensor platform."""
    config = hass.data[DOMAIN]["config"]
    chargers_data = hass.data[DOMAIN]["chargers_data"]
    monitored_conditions = config.options.get(CONF_MONITORED_CONDITIONS, ["status"])
    custom_units = config.options.get(CUSTOM_UNITS, {})
    entities = []
    for charger_data in chargers_data.chargers:
        for key in monitored_conditions:
            data = EASEE_ENTITIES[key]
            entity_type = data.get("type", "sensor")

            if entity_type == "sensor":
                _LOGGER.debug(
                    "Adding entity: %s (%s) for charger %s",
                    key,
                    entity_type,
                    charger_data.charger.name,
                )

                if data["units"] in custom_units:
                    data["units"] = CUSTOM_UNITS_TABLE[data["units"]]

                entities.append(
                    ChargerSensor(
                        charger_data=charger_data,
                        name=key,
                        state_key=data["key"],
                        units=data["units"],
                        convert_units_func=convert_units_funcs.get(
                            data["convert_units_func"], None
                        ),
                        attrs_keys=data["attrs"],
                        icon=data["icon"],
                        state_func=data.get("state_func", None),
                    )
                )

        monitored_days = config.options.get(MEASURED_CONSUMPTION_DAYS, [])
        consumption_unit = CUSTOM_UNITS_TABLE["kWh"] if "kWh" in custom_units else "kWh"
        for interval in monitored_days:
            _LOGGER.info("Will measure days: %s", interval)
            entities.append(
                ChargerConsumptionSensor(
                    charger_data.charger,
                    f"consumption_days_{interval}",
                    int(interval),
                    consumption_unit,
                )
            )

    chargers_data.entities.extend(entities)
    async_add_entities(entities)


class ChargerSensor(ChargerEntity):
    """Implementation of Easee charger sensor."""

    @property
    def state(self):
        """Return status."""
        return self._state


class ChargerConsumptionSensor(Entity):
    """Implementation of Easee charger sensor."""

    def __init__(self, charger, name, days, units):
        """Initialize the sensor."""
        self.charger = charger
        self._sensor_name = name
        self._days = days
        self._state = None
        self._units = units

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_charger_{self.charger.id}_{self._sensor_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.charger.id}_{self._sensor_name}"

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.charger.id)},
            "name": self.charger.name,
            "manufacturer": "Easee",
            "model": "Charging Robot",
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._units

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def state(self):
        """Return online status."""
        return round_2_dec(self._state, self._units)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {"name": self.charger.name, "id": self.charger.id}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:flash"

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug(
            "ChargerConsumptionSensor async_update : %s %s",
            self.charger.name,
            self._sensor_name,
        )
        now = datetime.now()
        self._state = await self.charger.get_consumption_between_dates(
            now - timedelta(0, 86400 * self._days), now
        )
