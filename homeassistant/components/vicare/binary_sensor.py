"""Viessmann ViCare sensor device."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_CONFIG_LIST, DOMAIN
from .entity import ViCareEntity
from .types import ViCareRequiredKeysMixin
from .utils import get_burners, get_circuits, get_compressors, is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass
class ViCareBinarySensorEntityDescription(
    BinarySensorEntityDescription, ViCareRequiredKeysMixin
):
    """Describes ViCare binary sensor entity."""


CIRCUIT_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="circulationpump_active",
        translation_key="circulation_pump",
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getCirculationPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="frost_protection_active",
        translation_key="frost_protection",
        icon="mdi:snowflake",
        value_getter=lambda api: api.getFrostProtectionActive(),
    ),
)

BURNER_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="burner_active",
        translation_key="burner",
        icon="mdi:gas-burner",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getActive(),
    ),
)

COMPRESSOR_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="compressor_active",
        translation_key="compressor",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getActive(),
    ),
)

GLOBAL_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="solar_pump_active",
        translation_key="solar_pump",
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getSolarPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="charging_active",
        translation_key="domestic_hot_water_charging",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getDomesticHotWaterChargingActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="dhw_circulationpump_active",
        translation_key="domestic_hot_water_circulation_pump",
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getDomesticHotWaterCirculationPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="dhw_pump_active",
        translation_key="domestic_hot_water_pump",
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getDomesticHotWaterPumpActive(),
    ),
)


def _build_entity(
    vicare_api: PyViCareDevice,
    device_config: PyViCareDeviceConfig,
    entity_description: ViCareBinarySensorEntityDescription,
):
    """Create a ViCare binary sensor entity."""
    if is_supported(entity_description.key, entity_description, vicare_api):
        return ViCareBinarySensor(
            vicare_api,
            device_config,
            entity_description,
        )
    return None


async def _entities_from_descriptions(
    hass: HomeAssistant,
    entities: list[ViCareBinarySensor],
    sensor_descriptions: tuple[ViCareBinarySensorEntityDescription, ...],
    iterables,
    device_config: PyViCareDeviceConfig,
) -> None:
    """Create entities from descriptions and list of burners/circuits."""
    for description in sensor_descriptions:
        for current in iterables:
            entity = await hass.async_add_executor_job(
                _build_entity,
                current,
                device_config,
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
    entities: list[ViCareBinarySensor] = []

    for device_config, device in hass.data[DOMAIN][config_entry.entry_id][
        DEVICE_CONFIG_LIST
    ]:
        for description in GLOBAL_SENSORS:
            entity = await hass.async_add_executor_job(
                _build_entity,
                device,
                device_config,
                description,
            )
            if entity is not None:
                entities.append(entity)

        circuits = await hass.async_add_executor_job(get_circuits, device)
        await _entities_from_descriptions(
            hass, entities, CIRCUIT_SENSORS, circuits, config_entry
        )

        burners = await hass.async_add_executor_job(get_burners, device)
        await _entities_from_descriptions(
            hass, entities, BURNER_SENSORS, burners, config_entry
        )

        compressors = await hass.async_add_executor_job(get_compressors, device)
        await _entities_from_descriptions(
            hass, entities, COMPRESSOR_SENSORS, compressors, config_entry
        )

    async_add_entities(entities)


class ViCareBinarySensor(ViCareEntity, BinarySensorEntity):
    """Representation of a ViCare sensor."""

    entity_description: ViCareBinarySensorEntityDescription

    def __init__(
        self,
        api: PyViCareDevice,
        device_config: PyViCareDeviceConfig,
        description: ViCareBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device_config, api, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_is_on is not None

    def update(self) -> None:
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
