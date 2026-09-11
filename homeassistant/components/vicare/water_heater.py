"""Viessmann ViCare water_heater device."""

from contextlib import suppress
from datetime import time as dt_time
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
from homeassistant.helpers.typing import VolDictType
from homeassistant.util import snakecase

from .const import DOMAIN
from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice
from .utils import get_circuits

_LOGGER = logging.getLogger(__name__)

VICARE_TEMP_WATER_MIN = 10
VICARE_TEMP_WATER_MAX = 60

SERVICE_SET_CIRCULATION_SCHEDULE = "set_circulation_schedule"

# Maps the full weekday service field names to the short keys PyViCare expects.
CIRCULATION_SCHEDULE_DAYS = (
    ("monday", "mon"),
    ("tuesday", "tue"),
    ("wednesday", "wed"),
    ("thursday", "thu"),
    ("friday", "fri"),
    ("saturday", "sat"),
    ("sunday", "sun"),
)
# ViCare represents midnight as the end of a slot using "24:00" rather than "00:00".
# The native time selector cannot express that, so an end time of exactly midnight
# is treated as the sentinel for "24:00" once serialized back to the ViCare API.
CIRCULATION_SCHEDULE_MIDNIGHT_END = "24:00"

# Maps the snake_case, translatable service field values to the raw ViCare
# circulation mode strings (which are not valid translation keys as-is).
CIRCULATION_SCHEDULE_MODES = (
    ("on", "on"),
    ("5_25_cycles", "5/25-cycles"),
    ("5_10_cycles", "5/10-cycles"),
)
CIRCULATION_SCHEDULE_MODE_TO_RAW = dict(CIRCULATION_SCHEDULE_MODES)


def _parse_end_time(value: Any) -> dt_time:
    """Parse a slot end time, accepting the literal "24:00" for midnight."""
    if value == CIRCULATION_SCHEDULE_MIDNIGHT_END:
        return dt_time(0, 0)
    return cv.time(value)


def _validate_slot_resolution(slot: dict[str, Any]) -> dict[str, Any]:
    """Validate that start/end times fall on a 10-minute resolution."""
    for key in ("start_time", "end_time"):
        value: dt_time = slot[key]
        if value.second or value.minute % 10 != 0:
            raise vol.Invalid(f"{key} must be at a 10-minute resolution: {value}")
    return slot


def _slot_minutes(slot: dict[str, Any]) -> tuple[int, int]:
    """Return a slot's (start, end) as minutes since midnight, 24:00 as 1440."""
    start_time: dt_time = slot["start_time"]
    end_time: dt_time = slot["end_time"]
    start = start_time.hour * 60 + start_time.minute
    end = 24 * 60 if end_time == dt_time(0, 0) else end_time.hour * 60 + end_time.minute
    return start, end


def _validate_slot_time_range(slot: dict[str, Any]) -> dict[str, Any]:
    """Validate that a slot's end time is after its start time."""
    start, end = _slot_minutes(slot)
    if end <= start:
        raise vol.Invalid(
            "end_time must be after start_time: "
            f"{slot['start_time']}-{slot['end_time']}"
        )
    return slot


CIRCULATION_SCHEDULE_SLOT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("start_time"): cv.time,
            vol.Required("end_time"): _parse_end_time,
            vol.Required("mode"): vol.In(CIRCULATION_SCHEDULE_MODE_TO_RAW),
            vol.Required("position"): vol.All(int, vol.Range(min=0)),
        }
    ),
    _validate_slot_resolution,
    _validate_slot_time_range,
)

CIRCULATION_SCHEDULE_SCHEMA: VolDictType = {
    vol.Required(day_name): vol.All(
        cv.ensure_list,
        [CIRCULATION_SCHEDULE_SLOT_SCHEMA],
    )
    for day_name, _ in CIRCULATION_SCHEDULE_DAYS
}


def _serialize_slot(slot: dict[str, Any]) -> dict[str, Any]:
    """Convert a validated schedule slot into the ViCare API's wire format."""
    end_time: dt_time = slot["end_time"]
    end = (
        CIRCULATION_SCHEDULE_MIDNIGHT_END
        if end_time == dt_time(0, 0)
        else end_time.strftime("%H:%M")
    )
    return {
        "start": slot["start_time"].strftime("%H:%M"),
        "end": end,
        "mode": CIRCULATION_SCHEDULE_MODE_TO_RAW[slot["mode"]],
        "position": slot["position"],
    }


def _slots_overlap(slots: list[dict[str, Any]]) -> bool:
    """Return True if any two slots overlap. Touching slots do not overlap."""
    max_end = 0
    for start, end in sorted(_slot_minutes(slot) for slot in slots):
        if start < max_end:
            return True
        max_end = max(max_end, end)
    return False


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
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_CIRCULATION_SCHEDULE,
        CIRCULATION_SCHEDULE_SCHEMA,
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
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = VICARE_TEMP_WATER_MIN
    _attr_max_temp = VICARE_TEMP_WATER_MAX
    _attr_translation_key = "domestic_hot_water"
    _current_mode: str | None = None
    _circuit_modes: list[str] | None = None
    _circulation_schedule_max_entries: int | None = None
    _circulation_schedule_modes: list[str] | None = None
    _circulation_schedule_overlap_allowed: bool | None = None

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
        # Populate modes/constraints before the entity is advertised, so
        # supported_features and schedule validation are correct immediately.
        self.update()

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
                self._attr_min_temp = self._api.getDomesticHotWaterMinTemperature()

            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_max_temp = self._api.getDomesticHotWaterMaxTemperature()

            with suppress(PyViCareNotSupportedFeatureError):
                self._circulation_schedule_modes = (
                    self._api.getDomesticHotWaterCirculationScheduleModes()
                )

            with suppress(PyViCareNotSupportedFeatureError, KeyError):
                self._circulation_schedule_max_entries = self._api.getProperty(
                    "heating.dhw.pumps.circulation.schedule"
                )["commands"]["setSchedule"]["params"]["newSchedule"]["constraints"][
                    "maxEntries"
                ]

            with suppress(PyViCareNotSupportedFeatureError, KeyError):
                self._circulation_schedule_overlap_allowed = self._api.getProperty(
                    "heating.dhw.pumps.circulation.schedule"
                )["commands"]["setSchedule"]["params"]["newSchedule"]["constraints"][
                    "overlapAllowed"
                ]

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._api.setDomesticHotWaterTemperature(temp)
            self._attr_target_temperature = temp

    @override
    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self._circuit.setMode(self._circuit_mode_map[operation_mode])

    def set_circulation_schedule(self, **schedule_by_day: list[dict[str, Any]]) -> None:
        """Set the DHW circulation pump schedule."""
        modes = self._circulation_schedule_modes
        if modes is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="circulation_schedule_not_supported",
            )

        max_entries = self._circulation_schedule_max_entries
        overlap_allowed = self._circulation_schedule_overlap_allowed
        for day, slots in schedule_by_day.items():
            if max_entries is not None and len(slots) > max_entries:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="circulation_schedule_too_many_slots",
                    translation_placeholders={
                        "day": day,
                        "max_entries": str(max_entries),
                    },
                )
            for slot in slots:
                if CIRCULATION_SCHEDULE_MODE_TO_RAW[slot["mode"]] not in modes:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="circulation_schedule_mode_not_supported",
                        translation_placeholders={
                            "day": day,
                            "mode": slot["mode"],
                            "modes": ", ".join(modes),
                        },
                    )
            if overlap_allowed is False and _slots_overlap(slots):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="circulation_schedule_overlap_not_allowed",
                    translation_placeholders={"day": day},
                )

        schedule = {
            short_day: [_serialize_slot(slot) for slot in schedule_by_day[full_day]]
            for full_day, short_day in CIRCULATION_SCHEDULE_DAYS
        }
        self._api.setDomesticHotWaterCirculationSchedule(schedule)

    @property
    def _circuit_mode_map(self) -> dict[str, str]:
        """Return the operation-mode-to-ViCare-circuit-mode mapping."""
        if self._circuit_modes is None:
            return {}
        return {snakecase(mode): mode for mode in self._circuit_modes}

    @property
    @override
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the supported features."""
        features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
        if self._circuit_modes:
            features |= WaterHeaterEntityFeature.OPERATION_MODE
        return features

    @property
    @override
    def operation_list(self) -> list[str] | None:
        """Return the list of operation modes supported by this circuit."""
        return list(self._circuit_mode_map) or None

    @property
    @override
    def current_operation(self) -> str | None:
        """Return the currently active ViCare circuit mode."""
        if self._current_mode is None:
            return None
        return snakecase(self._current_mode)
