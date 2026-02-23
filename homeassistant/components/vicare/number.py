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
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_HEAT_TIMEOUT_MINUTES,
    CONF_MIN_BOOST_TEMPERATURE,
    CONF_WARM_WATER_DELAY_MINUTES,
    DEFAULT_DHW_BOOST_HEAT_TIMEOUT_MINUTES,
    DEFAULT_DHW_BOOST_MIN_TEMPERATURE,
    DEFAULT_DHW_BOOST_WARM_WATER_DELAY_MINUTES,
    DOMAIN,
)
from .entity import ViCareEntity
from .types import (
    HeatingProgram,
    ViCareConfigEntry,
    ViCareDevice,
    ViCareRequiredKeysMixin,
)
from .utils import get_circuits, get_device_serial, is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViCareNumberEntityDescription(NumberEntityDescription, ViCareRequiredKeysMixin):
    """Describes ViCare number entity."""

    value_getter: Callable[[PyViCareDevice], float]
    value_setter: Callable[[PyViCareDevice, float], Any] | None = None
    min_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    max_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    stepping_getter: Callable[[PyViCareDevice], float | None] | None = None


@dataclass(frozen=True, kw_only=True)
class ViCareOptionNumberEntityDescription(NumberEntityDescription):
    """Describes ViCare option number entity."""

    option_key: str
    default_value: float


BOOST_OPTION_ENTITY_DESCRIPTIONS: tuple[ViCareOptionNumberEntityDescription, ...] = (
    ViCareOptionNumberEntityDescription(
        key="boost_min_temperature",
        translation_key="boost_min_temperature",
        option_key=CONF_MIN_BOOST_TEMPERATURE,
        default_value=DEFAULT_DHW_BOOST_MIN_TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=20,
        native_max_value=70,
        native_step=1,
    ),
    ViCareOptionNumberEntityDescription(
        key="boost_heat_timeout",
        translation_key="boost_heat_timeout",
        option_key=CONF_HEAT_TIMEOUT_MINUTES,
        default_value=float(DEFAULT_DHW_BOOST_HEAT_TIMEOUT_MINUTES),
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=10,
        native_max_value=240,
        native_step=10,
    ),
    ViCareOptionNumberEntityDescription(
        key="boost_warm_water_delay",
        translation_key="boost_warm_water_delay",
        option_key=CONF_WARM_WATER_DELAY_MINUTES,
        default_value=float(DEFAULT_DHW_BOOST_WARM_WATER_DELAY_MINUTES),
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=1,
        native_max_value=240,
        native_step=1,
    ),
)


DEVICE_ENTITY_DESCRIPTIONS: tuple[ViCareNumberEntityDescription, ...] = (
    ViCareNumberEntityDescription(
        key="dhw_temperature",
        translation_key="dhw_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_getter=lambda api: api.getDomesticHotWaterConfiguredTemperature(),
        value_setter=lambda api, value: api.setDomesticHotWaterTemperature(value),
        min_value_getter=lambda api: api.getDomesticHotWaterMinTemperature(),
        max_value_getter=lambda api: api.getDomesticHotWaterMaxTemperature(),
        native_step=1,
    ),
    ViCareNumberEntityDescription(
        key="dhw_secondary_temperature",
        translation_key="dhw_secondary_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_getter=lambda api: api.getDomesticHotWaterConfiguredTemperature2(),
        value_setter=lambda api, value: api.setDomesticHotWaterTemperature2(value),
        # no getters for min, max, stepping exposed yet, using static values
        native_min_value=10,
        native_max_value=60,
        native_step=1,
    ),
    ViCareNumberEntityDescription(
        key="dhw_hysteresis_switch_on",
        translation_key="dhw_hysteresis_switch_on",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        mode=NumberMode.BOX,
        value_getter=lambda api: api.getDomesticHotWaterHysteresisSwitchOn(),
        value_setter=lambda api, value: api.setDomesticHotWaterHysteresisSwitchOn(
            value
        ),
        min_value_getter=lambda api: api.getDomesticHotWaterHysteresisSwitchOnMin(),
        max_value_getter=lambda api: api.getDomesticHotWaterHysteresisSwitchOnMax(),
        stepping_getter=lambda api: api.getDomesticHotWaterHysteresisSwitchOnStepping(),
    ),
    ViCareNumberEntityDescription(
        key="dhw_hysteresis_switch_off",
        translation_key="dhw_hysteresis_switch_off",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        mode=NumberMode.BOX,
        value_getter=lambda api: api.getDomesticHotWaterHysteresisSwitchOff(),
        value_setter=lambda api, value: api.setDomesticHotWaterHysteresisSwitchOff(
            value
        ),
        min_value_getter=lambda api: api.getDomesticHotWaterHysteresisSwitchOffMin(),
        max_value_getter=lambda api: api.getDomesticHotWaterHysteresisSwitchOffMax(),
        stepping_getter=lambda api: (
            api.getDomesticHotWaterHysteresisSwitchOffStepping()
        ),
    ),
)


CIRCUIT_ENTITY_DESCRIPTIONS: tuple[ViCareNumberEntityDescription, ...] = (
    ViCareNumberEntityDescription(
        key="heating curve shift",
        translation_key="heating_curve_shift",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_getter=lambda api: api.getHeatingCurveShift(),
        value_setter=lambda api, shift: api.setHeatingCurve(
            shift, api.getHeatingCurveSlope()
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
        mode=NumberMode.BOX,
        value_getter=lambda api: api.getHeatingCurveSlope(),
        value_setter=lambda api, slope: api.setHeatingCurve(
            api.getHeatingCurveShift(), slope
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
        mode=NumberMode.BOX,
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
        mode=NumberMode.BOX,
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
        mode=NumberMode.BOX,
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
        mode=NumberMode.BOX,
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
        mode=NumberMode.BOX,
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
        mode=NumberMode.BOX,
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
    ViCareNumberEntityDescription(
        key="normal_cooling_temperature",
        translation_key="normal_cooling_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            HeatingProgram.NORMAL_COOLING
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            HeatingProgram.NORMAL_COOLING, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            HeatingProgram.NORMAL_COOLING
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            HeatingProgram.NORMAL_COOLING
        ),
        stepping_getter=lambda api: api.getProgramStepping(
            HeatingProgram.NORMAL_COOLING
        ),
    ),
    ViCareNumberEntityDescription(
        key="reduced_cooling_temperature",
        translation_key="reduced_cooling_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            HeatingProgram.REDUCED_COOLING
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            HeatingProgram.REDUCED_COOLING, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            HeatingProgram.REDUCED_COOLING
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            HeatingProgram.REDUCED_COOLING
        ),
        stepping_getter=lambda api: api.getProgramStepping(
            HeatingProgram.REDUCED_COOLING
        ),
    ),
    ViCareNumberEntityDescription(
        key="comfort_cooling_temperature",
        translation_key="comfort_cooling_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            HeatingProgram.COMFORT_COOLING
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            HeatingProgram.COMFORT_COOLING, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            HeatingProgram.COMFORT_COOLING
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            HeatingProgram.COMFORT_COOLING
        ),
        stepping_getter=lambda api: api.getProgramStepping(
            HeatingProgram.COMFORT_COOLING
        ),
    ),
)


def _build_entities(
    config_entry: ViCareConfigEntry,
    device_list: list[ViCareDevice],
) -> list[NumberEntity]:
    """Create ViCare number entities for a device."""

    entities: list[NumberEntity] = []
    primary_device = device_list[0] if device_list else None

    entities.extend(
        ViCareOptionNumber(config_entry, description, primary_device)
        for description in BOOST_OPTION_ENTITY_DESCRIPTIONS
    )

    for device in device_list:
        # add device entities
        entities.extend(
            ViCareNumber(
                description,
                get_device_serial(device.api),
                device.config,
                device.api,
            )
            for description in DEVICE_ENTITY_DESCRIPTIONS
            if is_supported(description.key, description.value_getter, device.api)
        )
        # add component entities
        entities.extend(
            ViCareNumber(
                description,
                get_device_serial(device.api),
                device.config,
                device.api,
                circuit,
            )
            for circuit in get_circuits(device.api)
            for description in CIRCUIT_ENTITY_DESCRIPTIONS
            if is_supported(description.key, description.value_getter, circuit)
        )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the ViCare number devices."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry,
            config_entry.runtime_data.devices,
        )
    )


class ViCareNumber(ViCareEntity, NumberEntity):
    """Representation of a ViCare number."""

    entity_description: ViCareNumberEntityDescription

    def __init__(
        self,
        description: ViCareNumberEntityDescription,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        component: PyViCareHeatingDeviceComponent | None = None,
    ) -> None:
        """Initialize the number."""
        super().__init__(
            description.key, device_serial, device_config, device, component
        )
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


class ViCareOptionNumber(NumberEntity):
    """Representation of a ViCare options-backed number."""

    entity_description: ViCareOptionNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ViCareConfigEntry,
        description: ViCareOptionNumberEntityDescription,
        device: ViCareDevice | None,
    ) -> None:
        """Initialize options-backed number entity."""
        self.entity_description = description
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}-{description.key}"
        self._attr_translation_key = description.translation_key
        if device is not None:
            gateway_serial = device.config.getConfig().serial
            device_id = device.config.getId()
            device_serial = get_device_serial(device.api)
            identifier = (
                f"{gateway_serial}_{device_serial.replace('-', '_')}"
                if device_serial is not None
                else f"{gateway_serial}_{device_id}"
            )
            model = device.config.getModel().replace("_", " ")
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, identifier)},
                name=model,
                manufacturer="Viessmann",
                model=model,
            )

    @property
    def native_value(self) -> float:
        """Return current value from entry options."""
        return float(
            self._config_entry.options.get(
                self.entity_description.option_key,
                self.entity_description.default_value,
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set option value."""
        options = dict(self._config_entry.options)
        options[self.entity_description.option_key] = value
        self.hass.config_entries.async_update_entry(self._config_entry, options=options)
        self.async_write_ha_state()
