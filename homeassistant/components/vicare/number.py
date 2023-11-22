"""Number for ViCare."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging
from typing import Any

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
from requests.exceptions import ConnectionError as RequestConnectionError

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ViCareRequiredKeysMixin
from .const import DOMAIN, VICARE_API, VICARE_DEVICE_CONFIG
from .entity import ViCareEntity
from .utils import is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass
class ViCareNumberEntityDescription(NumberEntityDescription, ViCareRequiredKeysMixin):
    """Describes ViCare number entity."""

    value_setter: Callable[[PyViCareDevice, float], Any] | None = None


CIRCUIT_ENTITY_DESCRIPTIONS: tuple[ViCareNumberEntityDescription, ...] = (
    ViCareNumberEntityDescription(
        key="heating curve shift",
        name="Heating curve shift",
        icon="mdi:plus-minus-variant",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getHeatingCurveShift(),
        value_setter=lambda api, shift: (
            api.setHeatingCurve(shift, api.getHeatingCurveSlope())
        ),
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=-13,
        native_max_value=40,
        native_step=1,
    ),
    ViCareNumberEntityDescription(
        key="heating curve slope",
        name="Heating curve slope",
        icon="mdi:slope-uphill",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getHeatingCurveSlope(),
        value_setter=lambda api, slope: (
            api.setHeatingCurve(api.getHeatingCurveShift(), slope)
        ),
        native_min_value=0.2,
        native_max_value=3.5,
        native_step=0.1,
    ),
)


def _build_entity(
    name: str,
    vicare_api: PyViCareHeatingDeviceWithComponent,
    device_config: PyViCareDeviceConfig,
    entity_description: ViCareNumberEntityDescription,
) -> ViCareNumber | None:
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare number devices."""
    api = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]

    entities: list[ViCareNumber] = []
    try:
        for circuit in api.circuits:
            suffix = ""
            if len(api.circuits) > 1:
                suffix = f" {circuit.id}"
            for description in CIRCUIT_ENTITY_DESCRIPTIONS:
                entity = await hass.async_add_executor_job(
                    _build_entity,
                    f"{description.name}{suffix}",
                    circuit,
                    hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG],
                    description,
                )
                if entity is not None:
                    entities.append(entity)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("No circuits found")

    async_add_entities(entities)


class ViCareNumber(ViCareEntity, NumberEntity):
    """Representation of a ViCare number."""

    entity_description: ViCareNumberEntityDescription

    def __init__(
        self,
        name: str,
        api: PyViCareHeatingDeviceWithComponent,
        device_config: PyViCareDeviceConfig,
        description: ViCareNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(device_config, api, description.key)
        self.entity_description = description
        self._attr_name = name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.value_setter:
            self.entity_description.value_setter(self._api, value)
        self.async_write_ha_state()

    def update(self) -> None:
        """Update state of number."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_native_value = self.entity_description.value_getter(
                    self._api
                )
        except RequestConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
