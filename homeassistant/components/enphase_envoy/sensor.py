"""Support for Enphase Envoy solar energy monitor."""
from __future__ import annotations

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import COORDINATOR, DOMAIN, NAME, SENSORS

ICON = "mdi:flash"
CONST_DEFAULT_HOST = "envoy"
_LOGGER = logging.getLogger(__name__)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSORS]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_IP_ADDRESS, default=CONST_DEFAULT_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default="envoy"): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_NAME, default=""): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up envoy sensor platform."""
    entry_data: dict[str, Any] = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: DataUpdateCoordinator = entry_data[COORDINATOR]
    name = entry_data[NAME]

    entities = []
    for sensor_description in SENSORS:
        if (
            sensor_description.key == "inverters"
            and coordinator.data.get("inverters_production") is not None
        ):
            for inverter in coordinator.data["inverters_production"]:
                entity_name: str = f"{name} {sensor_description.name} {inverter}"
                split_name = entity_name.split(" ")
                serial_number = split_name[-1]
                entities.append(
                    Envoy(
                        sensor_description,
                        entity_name,
                        name,
                        cast(str, config_entry.unique_id),
                        serial_number,
                        coordinator,
                    )
                )
        elif sensor_description.key != "inverters":
            sensor_description_key_data = coordinator.data.get(sensor_description.key)
            if (
                isinstance(sensor_description_key_data, str)
                and "not available" in sensor_description_key_data
            ):
                continue

            entity_name = f"{name} {sensor_description.name}"
            entities.append(
                Envoy(
                    sensor_description,
                    entity_name,
                    name,
                    cast(str, config_entry.unique_id),
                    None,
                    coordinator,
                )
            )

    async_add_entities(entities)


class Envoy(CoordinatorEntity, SensorEntity):
    """Envoy entity."""

    def __init__(
        self,
        description: SensorEntityDescription,
        name: str,
        device_name: str,
        device_serial_number: str,
        serial_number: str | None,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize Envoy entity."""
        self.entity_description = description
        self._name = name
        self._serial_number = serial_number
        self._device_name = device_name
        self._device_serial_number = device_serial_number

        super().__init__(coordinator)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str | None:
        """Return the unique id of the sensor."""
        if self._serial_number:
            return self._serial_number
        if self._device_serial_number:
            return f"{self._device_serial_number}_{self.entity_description.key}"
        return None

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.entity_description.key != "inverters":
            value = self.coordinator.data.get(self.entity_description.key)

        elif (
            self.entity_description.key == "inverters"
            and self.coordinator.data.get("inverters_production") is not None
        ):
            value = self.coordinator.data.get("inverters_production").get(
                self._serial_number
            )[0]
        else:
            return None

        return value

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return ICON

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if (
            self.entity_description.key == "inverters"
            and self.coordinator.data.get("inverters_production") is not None
        ):
            value = self.coordinator.data.get("inverters_production").get(
                self._serial_number
            )[1]
            return {"last_reported": value}

        return None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device_info of the device."""
        if not self._device_serial_number:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_serial_number))},
            name=self._device_name,
            model="Envoy",
            manufacturer="Enphase",
        )
