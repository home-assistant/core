"""Viessmann ViCare sensor device."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice, ViCareRequiredKeysMixin
from .utils import (
    get_burners,
    get_circuits,
    get_compressors,
    get_device_serial,
    is_supported,
)

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
    ViCareBinarySensorEntityDescription(
        key="one_time_charge",
        translation_key="one_time_charge",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getOneTimeCharge(),
    ),
)


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareBinarySensor]:
    """Create ViCare binary sensor entities for a device."""

    entities: list[ViCareBinarySensor] = []
    for device in device_list:
        # add device entities
        entities.extend(
            ViCareBinarySensor(
                description,
                get_device_serial(device.api),
                device.config,
                device.api,
            )
            for description in GLOBAL_SENSORS
            if is_supported(description.key, description.value_getter, device.api)
        )
        # add component entities
        for component_list, entity_description_list in (
            (get_circuits(device.api), CIRCUIT_SENSORS),
            (get_burners(device.api), BURNER_SENSORS),
            (get_compressors(device.api), COMPRESSOR_SENSORS),
        ):
            entities.extend(
                ViCareBinarySensor(
                    description,
                    get_device_serial(device.api),
                    device.config,
                    device.api,
                    component,
                )
                for component in component_list
                for description in entity_description_list
                if is_supported(description.key, description.value_getter, component)
            )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the ViCare binary sensor devices."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        )
    )


class ViCareBinarySensor(ViCareEntity, BinarySensorEntity):
    """Representation of a ViCare sensor."""

    entity_description: ViCareBinarySensorEntityDescription

    def __init__(
        self,
        description: ViCareBinarySensorEntityDescription,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        component: PyViCareHeatingDeviceComponent | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            description.key, device_serial, device_config, device, component
        )
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
