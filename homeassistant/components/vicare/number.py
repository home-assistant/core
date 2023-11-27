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
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
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
from .utils import get_circuits, is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass
class ViCareNumberEntityDescription(NumberEntityDescription, ViCareRequiredKeysMixin):
    """Describes ViCare number entity."""

    value_setter: Callable[[PyViCareDevice, float], Any] | None = None
    min_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    max_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    stepping_getter: Callable[[PyViCareDevice], float | None] | None = None


CIRCUIT_ENTITIES: tuple[ViCareNumberEntityDescription, ...] = (
    ViCareNumberEntityDescription(
        key="heating curve shift",
        translation_key="heating_curve_shift",
        icon="mdi:plus-minus-variant",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getHeatingCurveShift(),
        value_setter=lambda api, shift: (
            api.setHeatingCurve(shift, api.getHeatingCurveSlope())
        ),
        native_min_value=-13,
        native_max_value=40,
        native_step=1,
    ),
    ViCareNumberEntityDescription(
        key="heating curve slope",
        translation_key="heating_curve_slope",
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
    ViCareNumberEntityDescription(
        key="normal_temperature",
        translation_key="normal_temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram("normal"),
        value_setter=lambda api, value: api.setProgramTemperature("normal", value),
        min_value_getter=lambda api: api.getProgramMinTemperature("normal"),
        max_value_getter=lambda api: api.getProgramMaxTemperature("normal"),
        stepping_getter=lambda api: api.getProgramStepping("normal"),
    ),
    ViCareNumberEntityDescription(
        key="reduced_temperature",
        translation_key="reduced_temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram("reduced"),
        value_setter=lambda api, value: api.setProgramTemperature("reduced", value),
        min_value_getter=lambda api: api.getProgramMinTemperature("reduced"),
        max_value_getter=lambda api: api.getProgramMaxTemperature("reduced"),
        stepping_getter=lambda api: api.getProgramStepping("reduced"),
    ),
    ViCareNumberEntityDescription(
        key="comfort_temperature",
        translation_key="comfort_temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram("comfort"),
        value_setter=lambda api, value: api.setProgramTemperature("comfort", value),
        min_value_getter=lambda api: api.getProgramMinTemperature("comfort"),
        max_value_getter=lambda api: api.getProgramMaxTemperature("comfort"),
        stepping_getter=lambda api: api.getProgramStepping("comfort"),
    ),
    ViCareNumberEntityDescription(
        key="eco_temperature",
        translation_key="eco_temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram("eco"),
        value_setter=lambda api, value: api.setProgramTemperature("eco", value),
        min_value_getter=lambda api: api.getProgramMinTemperature("eco"),
        max_value_getter=lambda api: api.getProgramMaxTemperature("eco"),
        stepping_getter=lambda api: api.getProgramStepping("eco"),
    ),
)


def _build_entity(
    api: PyViCareHeatingDeviceComponent,
    device_config: PyViCareDeviceConfig,
    entity_description: ViCareNumberEntityDescription,
) -> ViCareNumber | None:
    """Create a ViCare number entity."""
    if is_supported(entity_description.key, entity_description, api):
        return ViCareNumber(
            api,
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
    device_config = hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG]
    entities: list[ViCareNumber] = []

    circuits = await hass.async_add_executor_job(get_circuits, api)
    for circuit in circuits:
        for description in CIRCUIT_ENTITIES:
            entity = await hass.async_add_executor_job(
                _build_entity,
                circuit,
                device_config,
                description,
            )
            if entity is not None:
                entities.append(entity)

    async_add_entities(entities)


class ViCareNumber(ViCareEntity, NumberEntity):
    """Representation of a ViCare number."""

    entity_description: ViCareNumberEntityDescription

    def __init__(
        self,
        api: PyViCareHeatingDeviceComponent,
        device_config: PyViCareDeviceConfig,
        description: ViCareNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(device_config, api, description.key)
        self.entity_description = description

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
                self._attr_native_value = float(
                    self.entity_description.value_getter(self._api)
                )

                if self.entity_description.min_value_getter:
                    min_value = self.entity_description.min_value_getter(self._api)
                    if min_value is not None:
                        self._attr_native_min_value = min_value

                if self.entity_description.max_value_getter:
                    max_value = self.entity_description.max_value_getter(self._api)
                    if max_value is not None:
                        self._attr_native_max_value = max_value

                if self.entity_description.stepping_getter:
                    stepping = self.entity_description.stepping_getter(self._api)
                    if stepping is not None:
                        self._attr_native_step = stepping
        except RequestConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
