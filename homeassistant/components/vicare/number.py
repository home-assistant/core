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

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_LIST, DOMAIN
from .entity import ViCareEntity
from .types import HeatingProgram, ViCareDevice, ViCareRequiredKeysMixin
from .utils import get_circuits, is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViCareNumberEntityDescription(NumberEntityDescription, ViCareRequiredKeysMixin):
    """Describes ViCare number entity."""

    value_getter: Callable[[PyViCareDevice], float]
    value_setter: Callable[[PyViCareDevice, float], Any] | None = None
    min_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    max_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    stepping_getter: Callable[[PyViCareDevice], float | None] | None = None


DEVICE_ENTITY_DESCRIPTIONS: tuple[ViCareNumberEntityDescription, ...] = (
    ViCareNumberEntityDescription(
        key="dhw_secondary_temperature",
        translation_key="dhw_secondary_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDomesticHotWaterConfiguredTemperature2(),
        value_setter=lambda api, value: api.setDomesticHotWaterTemperature2(value),
        # no getters for min, max, stepping exposed yet, using static values
        native_min_value=10,
        native_max_value=60,
        native_step=1,
    ),
)


CIRCUIT_ENTITY_DESCRIPTIONS: tuple[ViCareNumberEntityDescription, ...] = (
    ViCareNumberEntityDescription(
        key="heating curve shift",
        translation_key="heating_curve_shift",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getHeatingCurveShift(),
        value_setter=lambda api, shift: (
            api.setHeatingCurve(shift, api.getHeatingCurveSlope())
        ),
        min_value_getter=lambda api: api.getHeatingCurveShiftMin(),
        max_value_getter=lambda api: api.getHeatingCurveShiftMax(),
        stepping_getter=lambda api: api.getHeatingCurveShiftStepping(),
        native_min_value=-13,
        native_max_value=40,
        native_step=1,
    ),
    ViCareNumberEntityDescription(
        key="heating curve slope",
        translation_key="heating_curve_slope",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getHeatingCurveSlope(),
        value_setter=lambda api, slope: (
            api.setHeatingCurve(api.getHeatingCurveShift(), slope)
        ),
        min_value_getter=lambda api: api.getHeatingCurveSlopeMin(),
        max_value_getter=lambda api: api.getHeatingCurveSlopeMax(),
        stepping_getter=lambda api: api.getHeatingCurveSlopeStepping(),
        native_min_value=0.2,
        native_max_value=3.5,
        native_step=0.1,
    ),
    ViCareNumberEntityDescription(
        key="normal_temperature",
        translation_key="normal_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            HeatingProgram.NORMAL
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            HeatingProgram.NORMAL, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            HeatingProgram.NORMAL
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            HeatingProgram.NORMAL
        ),
        stepping_getter=lambda api: api.getProgramStepping(HeatingProgram.NORMAL),
    ),
    ViCareNumberEntityDescription(
        key="reduced_temperature",
        translation_key="reduced_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            HeatingProgram.REDUCED
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            HeatingProgram.REDUCED, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            HeatingProgram.REDUCED
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            HeatingProgram.REDUCED
        ),
        stepping_getter=lambda api: api.getProgramStepping(HeatingProgram.REDUCED),
    ),
    ViCareNumberEntityDescription(
        key="comfort_temperature",
        translation_key="comfort_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            HeatingProgram.COMFORT
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            HeatingProgram.COMFORT, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            HeatingProgram.COMFORT
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            HeatingProgram.COMFORT
        ),
        stepping_getter=lambda api: api.getProgramStepping(HeatingProgram.COMFORT),
    ),
    ViCareNumberEntityDescription(
        key="normal_heating_temperature",
        translation_key="normal_heating_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            HeatingProgram.NORMAL_HEATING
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            HeatingProgram.NORMAL_HEATING, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            HeatingProgram.NORMAL_HEATING
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            HeatingProgram.NORMAL_HEATING
        ),
        stepping_getter=lambda api: api.getProgramStepping(
            HeatingProgram.NORMAL_HEATING
        ),
    ),
    ViCareNumberEntityDescription(
        key="reduced_heating_temperature",
        translation_key="reduced_heating_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            HeatingProgram.REDUCED_HEATING
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            HeatingProgram.REDUCED_HEATING, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            HeatingProgram.REDUCED_HEATING
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            HeatingProgram.REDUCED_HEATING
        ),
        stepping_getter=lambda api: api.getProgramStepping(
            HeatingProgram.REDUCED_HEATING
        ),
    ),
    ViCareNumberEntityDescription(
        key="comfort_heating_temperature",
        translation_key="comfort_heating_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            HeatingProgram.COMFORT_HEATING
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            HeatingProgram.COMFORT_HEATING, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            HeatingProgram.COMFORT_HEATING
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            HeatingProgram.COMFORT_HEATING
        ),
        stepping_getter=lambda api: api.getProgramStepping(
            HeatingProgram.COMFORT_HEATING
        ),
    ),
)


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareNumber]:
    """Create ViCare number entities for a device."""

    entities: list[ViCareNumber] = [
        ViCareNumber(
            device.api,
            device.config,
            description,
        )
        for device in device_list
        for description in DEVICE_ENTITY_DESCRIPTIONS
        if is_supported(description.key, description, device.api)
    ]

    entities.extend(
        [
            ViCareNumber(
                circuit,
                device.config,
                description,
            )
            for device in device_list
            for circuit in get_circuits(device.api)
            for description in CIRCUIT_ENTITY_DESCRIPTIONS
            if is_supported(description.key, description, circuit)
        ]
    )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare number devices."""
    device_list = hass.data[DOMAIN][config_entry.entry_id][DEVICE_LIST]

    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            device_list,
        )
    )


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
        self.schedule_update_ha_state()

    def update(self) -> None:
        """Update state of number."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_native_value = self.entity_description.value_getter(
                    self._api
                )

                if min_value := _get_value(
                    self.entity_description.min_value_getter, self._api
                ):
                    self._attr_native_min_value = min_value

                if max_value := _get_value(
                    self.entity_description.max_value_getter, self._api
                ):
                    self._attr_native_max_value = max_value

                if stepping_value := _get_value(
                    self.entity_description.stepping_getter, self._api
                ):
                    self._attr_native_step = stepping_value
        except RequestConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)


def _get_value(
    fn: Callable[[PyViCareDevice], float | None] | None,
    api: PyViCareHeatingDeviceComponent,
) -> float | None:
    return None if fn is None else fn(api)
