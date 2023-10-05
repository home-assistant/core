"""Viessmann ViCare sensor device."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ViCareRequiredKeysMixin
from .const import DOMAIN, VICARE_API, VICARE_DEVICE_CONFIG, VICARE_NAME

_LOGGER = logging.getLogger(__name__)


@dataclass
class ViCareBinarySensorEntityDescription(
    BinarySensorEntityDescription, ViCareRequiredKeysMixin
):
    """Describes ViCare binary sensor entity."""


CIRCUIT_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="circulationpump",
        name="Circulation pump",
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getCirculationPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="frost_protection",
        name="Frost protection",
        icon="mdi:snowflake",
        device_class=None,
        value_getter=lambda api: api.getFrostProtectionActive(),
    ),
)

BURNER_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="burner",
        name="Burner",
        icon="mdi:fire",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getActive(),
    ),
)

COMPRESSOR_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="compressor_active",
        name="Compressor active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getActive(),
    ),
)

GLOBAL_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="solar_pump_active",
        name="Solar pump active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getSolarPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="charging_active",
        name="DHW Charging active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getDomesticHotWaterChargingActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="dhw_circulationpump_active",
        name="DHW Circulation Pump Active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getDomesticHotWaterCirculationPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="dhw_pump_active",
        name="DHW Pump Active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getDomesticHotWaterPumpActive(),
    ),
)


def _build_entity(name, vicare_api, device_config, sensor):
    """Create a ViCare binary sensor entity."""
    try:
        sensor.value_getter(vicare_api)
        _LOGGER.debug("Found entity %s", name)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("Feature not supported %s", name)
        return None
    except AttributeError:
        _LOGGER.debug("Attribute Error %s", name)
        return None

    return ViCareBinarySensor(
        name,
        vicare_api,
        device_config,
        sensor,
    )


async def _entities_from_descriptions(
    hass, name, entities, sensor_descriptions, iterables, config_entry
):
    """Create entities from descriptions and list of burners/circuits."""
    for description in sensor_descriptions:
        for current in iterables:
            suffix = ""
            if len(iterables) > 1:
                suffix = f" {current.id}"
            entity = await hass.async_add_executor_job(
                _build_entity,
                f"{name} {description.name}{suffix}",
                current,
                hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG],
                description,
            )
            if entity is not None:
                entities.append(entity)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare binary sensor devices."""
    name = VICARE_NAME
    api = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]

    entities = []

    for description in GLOBAL_SENSORS:
        entity = await hass.async_add_executor_job(
            _build_entity,
            f"{name} {description.name}",
            api,
            hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG],
            description,
        )
        if entity is not None:
            entities.append(entity)

    try:
        await _entities_from_descriptions(
            hass, name, entities, CIRCUIT_SENSORS, api.circuits, config_entry
        )
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("No circuits found")

    try:
        await _entities_from_descriptions(
            hass, name, entities, BURNER_SENSORS, api.burners, config_entry
        )
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("No burners found")

    try:
        await _entities_from_descriptions(
            hass, name, entities, COMPRESSOR_SENSORS, api.compressors, config_entry
        )
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("No compressors found")

    async_add_entities(entities)


class ViCareBinarySensor(BinarySensorEntity):
    """Representation of a ViCare sensor."""

    entity_description: ViCareBinarySensorEntityDescription

    def __init__(
        self, name, api, device_config, description: ViCareBinarySensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = name
        self._api = api
        self.entity_description = description
        self._device_config = device_config
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_config.getConfig().serial)},
            name=device_config.getModel(),
            manufacturer="Viessmann",
            model=device_config.getModel(),
            configuration_url="https://developer.viessmann.com/",
        )

    @property
    def available(self):
        """Return True if entity is available."""
        return self._attr_is_on is not None

    @property
    def unique_id(self) -> str:
        """Return unique ID for this device."""
        tmp_id = (
            f"{self._device_config.getConfig().serial}-{self.entity_description.key}"
        )
        if hasattr(self._api, "id"):
            return f"{tmp_id}-{self._api.id}"
        return tmp_id

    def update(self):
        """Update state of sensor."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_is_on = self.entity_description.value_getter(self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
