"""Viessmann ViCare sensor device."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceWithComponent,
)
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

from .const import DEVICE_LIST, DOMAIN
from .entity import ViCareEntity
from .types import ViCareDevice, ViCareRequiredKeysMixin
from .utils import get_burners, get_circuits, get_compressors, is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViCareBinarySensorEntityDescription(
    BinarySensorEntityDescription, ViCareRequiredKeysMixin
):
    """Describes ViCare binary sensor entity."""

    value_getter: Callable[[PyViCareDevice], bool]


CIRCUIT_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="circulationpump_active",
        translation_key="circulation_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getCirculationPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="frost_protection_active",
        translation_key="frost_protection",
        value_getter=lambda api: api.getFrostProtectionActive(),
    ),
)

BURNER_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="burner_active",
        translation_key="burner",
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
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getDomesticHotWaterCirculationPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="dhw_pump_active",
        translation_key="domestic_hot_water_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getDomesticHotWaterPumpActive(),
    ),
)


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareBinarySensor]:
    """Create ViCare binary sensor entities for a device."""

    entities: list[ViCareBinarySensor] = []
    for device in device_list:
        entities.extend(_build_entities_for_device(device.api, device.config))
        entities.extend(
            _build_entities_for_component(
                get_circuits(device.api), device.config, CIRCUIT_SENSORS
            )
        )
        entities.extend(
            _build_entities_for_component(
                get_burners(device.api), device.config, BURNER_SENSORS
            )
        )
        entities.extend(
            _build_entities_for_component(
                get_compressors(device.api), device.config, COMPRESSOR_SENSORS
            )
        )
    return entities


def _build_entities_for_device(
    device: PyViCareDevice,
    device_config: PyViCareDeviceConfig,
) -> list[ViCareBinarySensor]:
    """Create device specific ViCare binary sensor entities."""

    return [
        ViCareBinarySensor(
            device,
            device_config,
            description,
        )
        for description in GLOBAL_SENSORS
        if is_supported(description.key, description, device)
    ]


def _build_entities_for_component(
    components: list[PyViCareHeatingDeviceWithComponent],
    device_config: PyViCareDeviceConfig,
    entity_descriptions: tuple[ViCareBinarySensorEntityDescription, ...],
) -> list[ViCareBinarySensor]:
    """Create component specific ViCare binary sensor entities."""

    return [
        ViCareBinarySensor(
            component,
            device_config,
            description,
        )
        for component in components
        for description in entity_descriptions
        if is_supported(description.key, description, component)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare binary sensor devices."""
    device_list = hass.data[DOMAIN][config_entry.entry_id][DEVICE_LIST]

    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            device_list,
        )
    )


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
