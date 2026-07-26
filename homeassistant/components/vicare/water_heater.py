"""Viessmann ViCare water_heater device."""

from contextlib import suppress
import logging
from typing import Any, override

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import HeatingCircuit as PyViCareHeatingCircuit
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError
import voluptuous as vol

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice
from .utils import get_circuits, get_device_serial

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

SERVICE_SET_CIRCULATION_SCHEDULE = "set_circulation_schedule"

CIRCULATION_SCHEDULE_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
CIRCULATION_SCHEDULE_MAX_SLOTS_PER_DAY = 4
CIRCULATION_SCHEDULE_TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
# ViCare represents midnight as the end of a slot using "24:00" rather than "00:00".
CIRCULATION_SCHEDULE_END_TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$|^24:00$"


def _validate_slot_resolution(slot: dict[str, Any]) -> dict[str, Any]:
    """Validate that start/end times fall on a 10-minute resolution."""
    for key in ("start", "end"):
        if int(slot[key].split(":")[1]) % 10 != 0:
            raise vol.Invalid(f"{key} must be at a 10-minute resolution: {slot[key]}")
    return slot


CIRCULATION_SCHEDULE_SLOT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("start"): cv.matches_regex(CIRCULATION_SCHEDULE_TIME_PATTERN),
            vol.Required("end"): cv.matches_regex(
                CIRCULATION_SCHEDULE_END_TIME_PATTERN
            ),
            vol.Required("mode"): vol.In(["on"]),
            vol.Required("position"): vol.All(int, vol.Range(min=0)),
        }
    ),
    _validate_slot_resolution,
)

CIRCULATION_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Optional(day, default=list): vol.All(
            cv.ensure_list,
            [CIRCULATION_SCHEDULE_SLOT_SCHEMA],
            vol.Length(max=CIRCULATION_SCHEDULE_MAX_SLOTS_PER_DAY),
        )
        for day in CIRCULATION_SCHEDULE_WEEKDAYS
    }
)

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

# Same mapping, but for circuits that are also heating, so that toggling DHW
# does not disable space heating (e.g. dhwAndHeating <-> heating).
HA_TO_VICARE_HVAC_DHW_WITH_HEATING = {
    OPERATION_MODE_OFF: VICARE_MODE_HEATING,
    OPERATION_MODE_ON: VICARE_MODE_DHWANDHEATING,
}

VICARE_HEATING_ACTIVE_MODES = frozenset(
    {VICARE_MODE_HEATING, VICARE_MODE_DHWANDHEATING, VICARE_MODE_DHWANDHEATINGCOOLING}
)


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareWater]:
    """Create ViCare domestic hot water entities for a device."""

    return [
        ViCareWater(
            get_device_serial(device.api),
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
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_CIRCULATION_SCHEDULE,
        {vol.Required("schedule"): CIRCULATION_SCHEDULE_SCHEMA},
        "set_circulation_schedule",
    )

    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        )
    )


class ViCareWater(ViCareEntity, WaterHeaterEntity):
    """Representation of the ViCare domestic hot water device."""

    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = VICARE_TEMP_WATER_MIN
    _attr_max_temp = VICARE_TEMP_WATER_MAX
    _attr_operation_list = list(HA_TO_VICARE_HVAC_DHW)
    _attr_translation_key = "domestic_hot_water"
    _current_mode: str | None = None
    _circuit_modes: list[str] | None = None
    _dhw_active: bool | None = None
    _circulation_schedule: dict[str, Any] | None = None

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
                self._attr_current_temperature = (
                    self._api.getDomesticHotWaterStorageTemperature()
                )

            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_target_temperature = (
                    self._api.getDomesticHotWaterDesiredTemperature()
                )

            with suppress(PyViCareNotSupportedFeatureError):
                self._current_mode = self._circuit.getActiveMode()

            with suppress(PyViCareNotSupportedFeatureError):
                self._circuit_modes = self._circuit.getModes()

            with suppress(PyViCareNotSupportedFeatureError):
                self._dhw_active = self._api.getDomesticHotWaterActive()

            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_min_temp = self._api.getDomesticHotWaterMinTemperature()

            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_max_temp = self._api.getDomesticHotWaterMaxTemperature()

            with suppress(PyViCareNotSupportedFeatureError):
                self._circulation_schedule = (
                    self._api.getDomesticHotWaterCirculationSchedule()
                )

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._api.setDomesticHotWaterTemperature(temp)
            self._attr_target_temperature = temp

    @override
    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        mode_map = (
            HA_TO_VICARE_HVAC_DHW_WITH_HEATING
            if self._current_mode in VICARE_HEATING_ACTIVE_MODES
            else HA_TO_VICARE_HVAC_DHW
        )
        vicare_mode = mode_map[operation_mode]
        if self._circuit_modes is not None and vicare_mode not in self._circuit_modes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="operation_mode_not_supported",
                translation_placeholders={"mode": operation_mode},
            )
        self._circuit.setMode(vicare_mode)

    def set_circulation_schedule(self, schedule: dict[str, Any]) -> None:
        """Set the DHW circulation pump schedule."""
        self._api.setDomesticHotWaterCirculationSchedule(schedule)

    @property
    @override
    def current_operation(self) -> str | None:
        """Return current operation ie. heat, cool, idle."""
        if self._dhw_active is not None:
            return OPERATION_MODE_ON if self._dhw_active else OPERATION_MODE_OFF
        if self._current_mode is None:
            return None
        return VICARE_TO_HA_HVAC_DHW.get(self._current_mode)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            k: v
            for k, v in {
                "circulation_schedule": self._circulation_schedule,
            }.items()
            if v is not None
        }
