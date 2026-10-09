"""Viessmann ViCare water_heater device."""

from contextlib import suppress
from datetime import time
import logging
from typing import Any, override

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import HeatingCircuit as PyViCareHeatingCircuit
from PyViCare.PyViCareUtils import (
    PyViCareCommandError,
    PyViCareNotSupportedFeatureError,
)

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_MODE,
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import ViCareEntity
from .services import ATTR_FROM, ATTR_TO, WEEKDAYS
from .types import ViCareConfigEntry, ViCareDevice
from .utils import get_circuits

_LOGGER = logging.getLogger(__name__)

VICARE_MODE_DHW = "dhw"
VICARE_MODE_HEATING = "heating"
VICARE_MODE_DHWANDHEATING = "dhwAndHeating"
VICARE_MODE_DHWANDHEATINGCOOLING = "dhwAndHeatingCooling"
VICARE_MODE_FORCEDREDUCED = "forcedReduced"
VICARE_MODE_FORCEDNORMAL = "forcedNormal"
VICARE_MODE_OFF = "standby"

VICARE_TEMP_WATER_MIN = 10
VICARE_TEMP_WATER_MAX = 60

OPERATION_MODE_ON = "on"
OPERATION_MODE_OFF = "off"

VICARE_TO_HA_HVAC_DHW = {
    VICARE_MODE_DHW: OPERATION_MODE_ON,
    VICARE_MODE_DHWANDHEATING: OPERATION_MODE_ON,
    VICARE_MODE_DHWANDHEATINGCOOLING: OPERATION_MODE_ON,
    VICARE_MODE_HEATING: OPERATION_MODE_OFF,
    VICARE_MODE_FORCEDREDUCED: OPERATION_MODE_OFF,
    VICARE_MODE_FORCEDNORMAL: OPERATION_MODE_ON,
    VICARE_MODE_OFF: OPERATION_MODE_OFF,
}

HA_TO_VICARE_HVAC_DHW = {
    OPERATION_MODE_OFF: VICARE_MODE_OFF,
    OPERATION_MODE_ON: VICARE_MODE_DHW,
}


def _to_vicare_time(value: time) -> str:
    """Format a slot time for ViCare, which marks the end of the day as 24:00."""
    if value == time.max:
        return "24:00"
    return value.strftime("%H:%M")


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareWater]:
    """Create ViCare domestic hot water entities for a device."""

    return [
        ViCareWater(
            device.serial,
            device.config,
            device.api,
            circuit,
        )
        for device in device_list
        for circuit in get_circuits(device.api)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ViCare water heater platform."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        )
    )


class ViCareWater(ViCareEntity, WaterHeaterEntity):
    """Representation of the ViCare domestic hot water device."""

    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = VICARE_TEMP_WATER_MIN
    _attr_max_temp = VICARE_TEMP_WATER_MAX
    _attr_operation_list = list(HA_TO_VICARE_HVAC_DHW)
    _attr_translation_key = "domestic_hot_water"
    _current_mode: str | None = None
    _dhw_active: bool | None = None

    def __init__(
        self,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        circuit: PyViCareHeatingCircuit,
    ) -> None:
        """Initialize the DHW water_heater device."""
        super().__init__(circuit.id, device_serial, device_config, device)
        self._circuit = circuit
        self._attributes: dict[str, Any] = {}

    def update(self) -> None:
        """Let HA know there has been an update from the ViCare API."""
        with self.vicare_api_handler():
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_native_current_temperature = (
                    self._api.getDomesticHotWaterStorageTemperature()
                )

            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_native_target_temperature = (
                    self._api.getDomesticHotWaterDesiredTemperature()
                )

            with suppress(PyViCareNotSupportedFeatureError):
                self._current_mode = self._circuit.getActiveMode()

            with suppress(PyViCareNotSupportedFeatureError):
                self._dhw_active = self._api.getDomesticHotWaterActive()

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._api.setDomesticHotWaterTemperature(temp)
            self._attr_native_target_temperature = temp

    @property
    @override
    def current_operation(self) -> str | None:
        """Return current operation ie. heat, cool, idle."""
        if self._dhw_active is not None:
            return OPERATION_MODE_ON if self._dhw_active else OPERATION_MODE_OFF
        if self._current_mode is None:
            return None
        return VICARE_TO_HA_HVAC_DHW.get(self._current_mode)

    def get_circulation_schedule(self) -> ServiceResponse:
        """Return the DHW circulation pump schedule."""
        schedule = self._get_circulation_schedule()
        return {
            day: [
                {
                    ATTR_FROM: f"{slot['start']}:00",
                    ATTR_TO: f"{slot['end']}:00",
                    ATTR_MODE: slot["mode"],
                }
                for slot in sorted(
                    schedule[day[:3]], key=lambda entry: entry["position"]
                )
            ]
            for day in WEEKDAYS
        }

    def set_circulation_schedule(self, **slots_by_day: list[dict[str, Any]]) -> None:
        """Set the DHW circulation pump schedule, keeping days not passed."""
        schedule = self._get_circulation_schedule()
        new_schedule = {day[:3]: schedule[day[:3]] for day in WEEKDAYS}
        for day, slots in slots_by_day.items():
            new_schedule[day[:3]] = [
                {
                    "start": _to_vicare_time(slot[ATTR_FROM]),
                    "end": _to_vicare_time(slot[ATTR_TO]),
                    "mode": slot[ATTR_MODE],
                    "position": position,
                }
                for position, slot in enumerate(slots)
            ]
        try:
            self._api.setDomesticHotWaterCirculationSchedule(new_schedule)
        except PyViCareCommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="circulation_schedule_not_set",
                translation_placeholders={"error": str(err)},
            ) from err

    def _get_circulation_schedule(self) -> dict[str, Any]:
        """Return the raw circulation schedule or raise if unsupported."""
        try:
            return self._api.getDomesticHotWaterCirculationSchedule()
        except PyViCareNotSupportedFeatureError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="circulation_schedule_not_supported",
            ) from err
