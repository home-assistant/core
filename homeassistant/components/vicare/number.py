"""Number for ViCare."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareDevice import Device
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ViCareRequiredKeysMixin
from .const import DOMAIN, VICARE_API, VICARE_DEVICE_CONFIG
from .entity import ViCareEntity
from .utils import is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass
class ViCareNumberEntityDescription(NumberEntityDescription, ViCareRequiredKeysMixin):
    """Describes ViCare sensor entity."""

    value_setter: Callable[[Device, float], str | None] | None = None
    min_getter: Callable[[Device], str | None] | None = None
    max_getter: Callable[[Device], str | None] | None = None
    step_getter: Callable[[Device], str | None] | None = None


CIRCUIT_SENSORS: tuple[ViCareNumberEntityDescription, ...] = (
    ViCareNumberEntityDescription(
        key="heating curve shift",
        name="Heating Curve Shift",
        icon="mdi:plus-minus-variant",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getHeatingCurveShift(),
        value_setter=lambda api, shift: api.setHeatingCurve(
            shift, api.getHeatingCurveSlope()
        ),
        min_getter=lambda api: api.getHeatingCurveShiftMin(),
        max_getter=lambda api: api.getHeatingCurveShiftMax(),
        step_getter=lambda api: api.getHeatingCurveShiftStepping(),
    ),
    ViCareNumberEntityDescription(
        key="heating curve slope",
        name="Heating Curve Slope",
        icon="mdi:slope-uphill",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getHeatingCurveSlope(),
        value_setter=lambda api, slope: api.setHeatingCurve(
            api.getHeatingCurveShift(), slope
        ),
        min_getter=lambda api: api.getHeatingCurveSlopeMin(),
        max_getter=lambda api: api.getHeatingCurveSlopeMax(),
        step_getter=lambda api: api.getHeatingCurveSlopeStepping(),
    ),
)


def _build_entity(
    name: str,
    vicare_api,
    device_config: PyViCareDeviceConfig,
    entity_description: ViCareNumberEntityDescription,
):
    """Create a ViCare number entity."""
    _LOGGER.debug("Found device %s", name)
    if is_supported(name, entity_description, vicare_api):
        return ViCareNumber(
            name,
            vicare_api,
            device_config,
            entity_description,
        )
    return None


async def _entities_from_descriptions(
    hass: HomeAssistant,
    entities: list[ViCareNumber],
    sensor_descriptions: tuple[ViCareNumberEntityDescription, ...],
    iterables,
    config_entry: ConfigEntry,
) -> None:
    """Create entities from descriptions and list of burners/circuits."""
    for description in sensor_descriptions:
        for current in iterables:
            suffix = ""
            if len(iterables) > 1:
                suffix = f" {current.id}"
            entity = await hass.async_add_executor_job(
                _build_entity,
                f"{description.name}{suffix}",
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
    """Create the ViCare sensor devices."""
    api = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]

    entities: list[ViCareNumber] = []
    try:
        await _entities_from_descriptions(
            hass, entities, CIRCUIT_SENSORS, api.circuits, config_entry
        )
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("No circuits found")

    async_add_entities(entities)


class ViCareNumber(ViCareEntity, NumberEntity):
    """Representation of a ViCare sensor."""

    entity_description: ViCareNumberEntityDescription

    def __init__(
        self, name, api, device_config, description: ViCareNumberEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device_config)
        self.entity_description = description
        self._attr_name = name
        self._api = api
        self._device_config = device_config

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.value_setter:
            self.entity_description.value_setter(self._api, value)
        self.async_write_ha_state()

    def update(self):
        """Update state of sensor."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_native_value = self.entity_description.value_getter(
                    self._api
                )

                if self.entity_description.min_getter:
                    min_value = self.entity_description.min_getter(self._api)
                    if min_value is not None:
                        self._attr_native_min_value = min_value

                if self.entity_description.max_getter:
                    max_value = self.entity_description.max_getter(self._api)
                    if max_value is not None:
                        self._attr_native_max_value = max_value

                if self.entity_description.step_getter:
                    step_value = self.entity_description.step_getter(self._api)
                    if step_value is not None:
                        self._attr_native_step = step_value

        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
