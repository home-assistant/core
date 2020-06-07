"""Support for Awair sensors."""

from typing import Callable, List, Optional

from python_awair.devices import AwairDevice
import voluptuous as vol

from homeassistant.components.awair import AwairDataUpdateCoordinator, AwairResult
from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ACCESS_TOKEN
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import slugify

from .const import (
    API_DUST,
    API_SCORE,
    API_TEMP,
    API_VOC,
    ATTR_ICON,
    ATTR_LABEL,
    ATTR_UNIT,
    ATTRIBUTION,
    DOMAIN,
    DUST_ALIASES,
    LOGGER,
    SENSOR_TYPES,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_ACCESS_TOKEN): cv.string}, extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import Awair configuration from YAML."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigType,
    async_add_entities: Callable[[List[Entity], bool], None],
):
    """Set up Awair sensor entity based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    sensors = []

    data: List[AwairResult] = coordinator.data.values()
    for result in data:
        if result.air_data:
            sensors.append(AwairSensor(API_SCORE, result.device, coordinator))
            device_sensors = result.air_data.sensors.keys()
            for sensor in device_sensors:
                if sensor in SENSOR_TYPES:
                    sensors.append(AwairSensor(sensor, result.device, coordinator))

            # The "DUST" sensor for Awair is a combo pm2.5/pm10 sensor only
            # present on first-gen devices in lieu of separate pm2.5/pm10 sensors.
            # We handle that by creating fake pm2.5/pm10 sensors that will always
            # report identical values, and we let users decide how they want to use
            # that data - because we can't really tell what kind of particles the
            # "DUST" sensor actually detected. However, it's still useful data.
            if API_DUST in device_sensors:
                for alias_kind in DUST_ALIASES:
                    sensors.append(AwairSensor(alias_kind, result.device, coordinator))

    async_add_entities(sensors)


class AwairSensor(Entity):
    """Defines an Awair sensor entity."""

    def __init__(
        self, kind: str, device: AwairDevice, coordinator: AwairDataUpdateCoordinator,
    ) -> None:
        """Set up an individual AwairSensor."""
        LOGGER.debug("Setting up %s: %s", kind, device.uuid)
        self.__kind = kind
        self.__device = device
        self.__coordinator = coordinator

        entity_id_name = SENSOR_TYPES[self.__kind][ATTR_DEVICE_CLASS]
        if self.__device.name:
            entity_id_name = f"{self.__device.name} {entity_id_name}"

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_id_name, hass=self.__coordinator.hass
        )

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        name = SENSOR_TYPES[self.__kind][ATTR_LABEL]
        if self.__device.name:
            name = f"{self.__device.name} {name}"

        return name

    @property
    def unique_id(self) -> str:
        """Return the uuid as the unique_id."""
        return f"{self.__device.uuid}-{SENSOR_TYPES[self.__kind][ATTR_DEVICE_CLASS]}"

    @property
    def available(self) -> bool:
        """Determine if the sensor is available based on API results."""
        # If the last update was successful...
        if self.__coordinator.last_update_success and self.__air_data:
            # and the results included our sensor type...
            if self.__kind in self.__air_data.sensors:
                # then we are available.
                return True

            # or, we're a dust alias
            if self.__kind in DUST_ALIASES and API_DUST in self.__air_data.sensors:
                return True

            # or we are API_SCORE
            if self.__kind == API_SCORE:
                # then we are available.
                return True

        # Otherwise, we are not.
        return False

    @property
    def state(self) -> float:
        """Return the state, rounding off to reasonable values."""
        state: float

        # Special-case for "SCORE", which we treat as the AQI
        if self.__kind == API_SCORE:
            state = self.__air_data.score
        elif self.__kind in DUST_ALIASES and API_DUST in self.__air_data.sensors:
            state = self.__air_data.sensors.dust
        else:
            state = self.__air_data.sensors[self.__kind]

        if self.__kind == API_VOC or self.__kind == API_SCORE:
            return round(state)

        if self.__kind == API_TEMP:
            return round(state, 1)

        return round(state, 2)

    @property
    def icon(self) -> str:
        """Return the icon."""
        return SENSOR_TYPES[self.__kind][ATTR_ICON]

    @property
    def device_class(self) -> str:
        """Return the device_class."""
        return SENSOR_TYPES[self.__kind][ATTR_DEVICE_CLASS]

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        return SENSOR_TYPES[self.__kind][ATTR_UNIT]

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def device_state_attributes(self) -> dict:
        """Return the Awair Index alongside state attributes.

        The Awair Index is a subjective score ranging from 0-4 (inclusive) that
        is is used by the Awair app when displaying the relative "safety" of a
        given measurement. Each value is mapped to a color indicating the safety:

            0: green
            1: yellow
            2: light-orange
            3: orange
            4: red

        The API indicates that both positive and negative values may be returned,
        but the negative values are mapped to identical colors as the positive values.
        Knowing that, we just return the absolute value of a given index so that
        users don't have to handle positive/negative values that ultimately "mean"
        the same thing.

        https://docs.developer.getawair.com/?version=latest#awair-score-and-index
        """
        attrs = {}
        label = slugify(SENSOR_TYPES[self.__kind][ATTR_DEVICE_CLASS])

        if self.__kind in self.__air_data.indices:
            attrs[f"{label}_awair_index"] = abs(self.__air_data.indices[self.__kind])
        elif self.__kind in DUST_ALIASES and API_DUST in self.__air_data.indices:
            attrs[f"{label}_awair_index"] = abs(self.__air_data.indices.dust)

        return attrs

    @property
    def device_info(self) -> dict:
        """Device information."""
        info = {
            "identifiers": {(DOMAIN, self.__device.uuid)},
            "manufacturer": "Awair",
            "model": self.__device.model,
        }

        if self.__device.name:
            info["name"] = self.__device.name

        if self.__device.mac_address:
            info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, self.__device.mac_address)
            }

        return info

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.__coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from update signal."""
        self.__coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self) -> None:
        """Update Awair entity."""
        await self.__coordinator.async_request_refresh()

    @property
    def __air_data(self) -> Optional[AwairResult]:
        """Return the latest data for our device, or None."""
        result: Optional[AwairResult] = self.__coordinator.data.get(
            self.__device.uuid, None
        )
        if result:
            return result.air_data
