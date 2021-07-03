"""Support for Enphase Envoy solar energy monitor."""

import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, NAME, SENSORS

ICON = "mdi:flash"
CONST_DEFAULT_HOST = "envoy"
_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_IP_ADDRESS, default=CONST_DEFAULT_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default="envoy"): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)): vol.All(
            cv.ensure_list, [vol.In(list(SENSORS))]
        ),
        vol.Optional(CONF_NAME, default=""): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Enphase Envoy sensor."""
    _LOGGER.warning(
        "Loading enphase_envoy via platform config is deprecated; The configuration"
        " has been migrated to a config entry and can be safely removed"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up envoy sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data[COORDINATOR]
    name = data[NAME]

    entities = []
    for condition in SENSORS:
        entity_name = ""
        if (
            condition == "inverters"
            and coordinator.data.get("inverters_production") is not None
        ):
            for inverter in coordinator.data["inverters_production"]:
                entity_name = f"{name} {SENSORS[condition][0]} {inverter}"
                split_name = entity_name.split(" ")
                serial_number = split_name[-1]
                entities.append(
                    Envoy(
                        condition,
                        entity_name,
                        name,
                        config_entry.unique_id,
                        serial_number,
                        SENSORS[condition][1],
                        SENSORS[condition][2],
                        coordinator,
                    )
                )
        elif condition != "inverters":
            data = coordinator.data.get(condition)
            if isinstance(data, str) and "not available" in data:
                continue

            entity_name = f"{name} {SENSORS[condition][0]}"
            entities.append(
                Envoy(
                    condition,
                    entity_name,
                    name,
                    config_entry.unique_id,
                    None,
                    SENSORS[condition][1],
                    SENSORS[condition][2],
                    coordinator,
                )
            )

    async_add_entities(entities)


class Envoy(CoordinatorEntity, SensorEntity):
    """Envoy entity."""

    def __init__(
        self,
        sensor_type,
        name,
        device_name,
        device_serial_number,
        serial_number,
        unit,
        state_class,
        coordinator,
    ):
        """Initialize Envoy entity."""
        self._type = sensor_type
        self._name = name
        self._serial_number = serial_number
        self._device_name = device_name
        self._device_serial_number = device_serial_number
        self._unit_of_measurement = unit
        self._attr_state_class = state_class

        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        if self._serial_number:
            return self._serial_number
        if self._device_serial_number:
            return f"{self._device_serial_number}_{self._type}"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._type != "inverters":
            value = self.coordinator.data.get(self._type)

        elif (
            self._type == "inverters"
            and self.coordinator.data.get("inverters_production") is not None
        ):
            value = self.coordinator.data.get("inverters_production").get(
                self._serial_number
            )[0]
        else:
            return None

        return value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if (
            self._type == "inverters"
            and self.coordinator.data.get("inverters_production") is not None
        ):
            value = self.coordinator.data.get("inverters_production").get(
                self._serial_number
            )[1]
            return {"last_reported": value}

        return None

    @property
    def device_info(self):
        """Return the device_info of the device."""
        if not self._device_serial_number:
            return None
        return {
            "identifiers": {(DOMAIN, str(self._device_serial_number))},
            "name": self._device_name,
            "model": "Envoy",
            "manufacturer": "Enphase",
        }
