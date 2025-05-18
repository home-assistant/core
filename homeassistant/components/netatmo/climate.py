"""Support for Netatmo Smart thermostats."""

from __future__ import annotations

import logging
from typing import Any, cast

from pyatmo.modules import NATherm1
from pyatmo.modules.device_types import DeviceType
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    DEFAULT_MIN_TEMP,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    STATE_OFF,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_END_DATETIME,
    ATTR_HEATING_POWER_REQUEST,
    ATTR_SCHEDULE_NAME,
    ATTR_SELECTED_SCHEDULE,
    ATTR_TARGET_TEMPERATURE,
    ATTR_TIME_PERIOD,
    DATA_SCHEDULES,
    DOMAIN,
    EVENT_TYPE_CANCEL_SET_POINT,
    EVENT_TYPE_SCHEDULE,
    EVENT_TYPE_SET_POINT,
    EVENT_TYPE_THERM_MODE,
    NETATMO_CREATE_CLIMATE,
    SERVICE_CLEAR_TEMPERATURE_SETTING,
    SERVICE_SET_PRESET_MODE_WITH_END_DATETIME,
    SERVICE_SET_SCHEDULE,
    SERVICE_SET_TEMPERATURE_WITH_END_DATETIME,
    SERVICE_SET_TEMPERATURE_WITH_TIME_PERIOD,
)
from .data_handler import HOME, SIGNAL_NAME, NetatmoRoom
from .entity import NetatmoRoomEntity

_LOGGER = logging.getLogger(__name__)

PRESET_FROST_GUARD = "frost_guard"
PRESET_SCHEDULE = "schedule"
PRESET_MANUAL = "manual"

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)
SUPPORT_PRESET = [PRESET_AWAY, PRESET_BOOST, PRESET_FROST_GUARD, PRESET_SCHEDULE]

THERM_MODES = (PRESET_SCHEDULE, PRESET_FROST_GUARD, PRESET_AWAY)

STATE_NETATMO_SCHEDULE = "schedule"
STATE_NETATMO_HG = "hg"
STATE_NETATMO_MAX = "max"
STATE_NETATMO_AWAY = PRESET_AWAY
STATE_NETATMO_OFF = STATE_OFF
STATE_NETATMO_MANUAL = "manual"
STATE_NETATMO_HOME = "home"

PRESET_MAP_NETATMO = {
    PRESET_FROST_GUARD: STATE_NETATMO_HG,
    PRESET_BOOST: STATE_NETATMO_MAX,
    PRESET_SCHEDULE: STATE_NETATMO_SCHEDULE,
    PRESET_AWAY: STATE_NETATMO_AWAY,
    STATE_NETATMO_OFF: STATE_NETATMO_OFF,
}

NETATMO_MAP_PRESET = {
    STATE_NETATMO_HG: PRESET_FROST_GUARD,
    STATE_NETATMO_MAX: PRESET_BOOST,
    STATE_NETATMO_SCHEDULE: PRESET_SCHEDULE,
    STATE_NETATMO_AWAY: PRESET_AWAY,
    STATE_NETATMO_OFF: STATE_NETATMO_OFF,
    STATE_NETATMO_MANUAL: STATE_NETATMO_MANUAL,
    STATE_NETATMO_HOME: PRESET_SCHEDULE,
}

HVAC_MAP_NETATMO = {
    PRESET_SCHEDULE: HVACMode.AUTO,
    STATE_NETATMO_HG: HVACMode.AUTO,
    PRESET_FROST_GUARD: HVACMode.AUTO,
    PRESET_BOOST: HVACMode.HEAT,
    STATE_NETATMO_OFF: HVACMode.OFF,
    STATE_NETATMO_MANUAL: HVACMode.AUTO,
    PRESET_MANUAL: HVACMode.AUTO,
    STATE_NETATMO_AWAY: HVACMode.AUTO,
}

CURRENT_HVAC_MAP_NETATMO = {True: HVACAction.HEATING, False: HVACAction.IDLE}

DEFAULT_MAX_TEMP = 30

NA_THERM = DeviceType.NATherm1
NA_VALVE = DeviceType.NRV


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo energy platform."""

    @callback
    def _create_entity(netatmo_device: NetatmoRoom) -> None:
        if not netatmo_device.room.climate_type:
            msg = f"No climate type found for this room: {netatmo_device.room.name}"
            _LOGGER.debug(msg)
            return
        entity = NetatmoThermostat(netatmo_device)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_CLIMATE, _create_entity)
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        {vol.Required(ATTR_SCHEDULE_NAME): cv.string},
        "_async_service_set_schedule",
    )
    platform.async_register_entity_service(
        SERVICE_SET_PRESET_MODE_WITH_END_DATETIME,
        {
            vol.Required(ATTR_PRESET_MODE): vol.In(THERM_MODES),
            vol.Required(ATTR_END_DATETIME): cv.datetime,
        },
        "_async_service_set_preset_mode_with_end_datetime",
    )
    platform.async_register_entity_service(
        SERVICE_SET_TEMPERATURE_WITH_END_DATETIME,
        {
            vol.Required(ATTR_TARGET_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=7, max=30)
            ),
            vol.Required(ATTR_END_DATETIME): cv.datetime,
        },
        "_async_service_set_temperature_with_end_datetime",
    )
    platform.async_register_entity_service(
        SERVICE_SET_TEMPERATURE_WITH_TIME_PERIOD,
        {
            vol.Required(ATTR_TARGET_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=7, max=30)
            ),
            vol.Required(ATTR_TIME_PERIOD): vol.All(
                cv.time_period,
                cv.positive_timedelta,
            ),
        },
        "_async_service_set_temperature_with_time_period",
    )
    platform.async_register_entity_service(
        SERVICE_CLEAR_TEMPERATURE_SETTING,
        None,
        "_async_service_clear_temperature_setting",
    )


class NetatmoThermostat(NetatmoRoomEntity, ClimateEntity):
    """Representation a Netatmo thermostat."""

    _attr_hvac_mode = HVACMode.AUTO
    _attr_max_temp = DEFAULT_MAX_TEMP
    _attr_preset_modes = SUPPORT_PRESET
    _attr_supported_features = SUPPORT_FLAGS
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "thermostat"
    _attr_name = None
    _away: bool | None = None
    _connected: bool | None = None

    _away_temperature: float | None = None
    _hg_temperature: float | None = None
    _boilerstatus: bool | None = None

    def __init__(self, room: NetatmoRoom) -> None:
        """Initialize the sensor."""
        super().__init__(room)

        self._signal_name = f"{HOME}-{self.home.entity_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._selected_schedule = None

        self._attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT]
        if self.device_type is NA_THERM:
            self._attr_hvac_modes.append(HVACMode.OFF)

        self._attr_unique_id = f"{self.device.entity_id}-{self.device_type}"

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        for event_type in (
            EVENT_TYPE_SET_POINT,
            EVENT_TYPE_THERM_MODE,
            EVENT_TYPE_CANCEL_SET_POINT,
            EVENT_TYPE_SCHEDULE,
        ):
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{event_type}",
                    self.handle_event,
                )
            )

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]

        if self.home.entity_id != data["home_id"]:
            return

        if data["event_type"] == EVENT_TYPE_SCHEDULE:
            # handle schedule change
            if "schedule_id" in data:
                self._selected_schedule = getattr(
                    self.hass.data[DOMAIN][DATA_SCHEDULES][self.home.entity_id].get(
                        data["schedule_id"]
                    ),
                    "name",
                    None,
                )
                self._attr_extra_state_attributes[ATTR_SELECTED_SCHEDULE] = (
                    self._selected_schedule
                )
                self.async_write_ha_state()
                self.data_handler.async_force_update(self._signal_name)
            # ignore other schedule events
            return

        home = data["home"]

        if self.home.entity_id != home["id"]:
            return

        if data["event_type"] == EVENT_TYPE_THERM_MODE:
            self._attr_preset_mode = NETATMO_MAP_PRESET[home[EVENT_TYPE_THERM_MODE]]
            self._attr_hvac_mode = HVAC_MAP_NETATMO[self._attr_preset_mode]
            if self._attr_preset_mode == PRESET_FROST_GUARD:
                self._attr_target_temperature = self._hg_temperature
            elif self._attr_preset_mode == PRESET_AWAY:
                self._attr_target_temperature = self._away_temperature
            elif self._attr_preset_mode in [PRESET_SCHEDULE, PRESET_HOME]:
                self.async_update_callback()
                self.data_handler.async_force_update(self._signal_name)
            self.async_write_ha_state()
            return

        for room in home.get("rooms", []):
            if (
                data["event_type"] == EVENT_TYPE_SET_POINT
                and self.device.entity_id == room["id"]
            ):
                if room["therm_setpoint_mode"] == STATE_NETATMO_OFF:
                    self._attr_hvac_mode = HVACMode.OFF
                    self._attr_preset_mode = STATE_NETATMO_OFF
                    self._attr_target_temperature = 0
                elif room["therm_setpoint_mode"] == STATE_NETATMO_MAX:
                    self._attr_hvac_mode = HVACMode.HEAT
                    self._attr_preset_mode = PRESET_MAP_NETATMO[PRESET_BOOST]
                    self._attr_target_temperature = DEFAULT_MAX_TEMP
                elif room["therm_setpoint_mode"] == STATE_NETATMO_MANUAL:
                    self._attr_hvac_mode = HVACMode.HEAT
                    self._attr_target_temperature = room["therm_setpoint_temperature"]
                else:
                    self._attr_target_temperature = room["therm_setpoint_temperature"]
                    if self._attr_target_temperature == DEFAULT_MAX_TEMP:
                        self._attr_hvac_mode = HVACMode.HEAT
                self.async_write_ha_state()
                return

            if (
                data["event_type"] == EVENT_TYPE_CANCEL_SET_POINT
                and self.device.entity_id == room["id"]
            ):
                if self._attr_hvac_mode == HVACMode.OFF:
                    self._attr_hvac_mode = HVACMode.AUTO
                    self._attr_preset_mode = PRESET_MAP_NETATMO[PRESET_SCHEDULE]

                self.async_update_callback()
                self.async_write_ha_state()
                return

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported."""
        if self.device_type != NA_VALVE and self._boilerstatus is not None:
            return CURRENT_HVAC_MAP_NETATMO[self._boilerstatus]
        # Maybe it is a valve
        if (
            heating_req := getattr(self.device, "heating_power_request", 0)
        ) is not None and heating_req > 0:
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.AUTO:
            await self.async_set_preset_mode(PRESET_SCHEDULE)
        elif hvac_mode == HVACMode.HEAT:
            await self.async_set_preset_mode(PRESET_BOOST)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if (
            preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX)
            and self.device_type == NA_VALVE
            and self._attr_hvac_mode == HVACMode.HEAT
        ):
            await self.device.async_therm_set(
                STATE_NETATMO_HOME,
            )
        elif (
            preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX)
            and self.device_type == NA_VALVE
        ):
            await self.device.async_therm_set(
                STATE_NETATMO_MANUAL,
                DEFAULT_MAX_TEMP,
            )
        elif (
            preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX)
            and self._attr_hvac_mode == HVACMode.HEAT
        ):
            await self.device.async_therm_set(STATE_NETATMO_HOME)
        elif preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX):
            await self.device.async_therm_set(PRESET_MAP_NETATMO[preset_mode])
        elif preset_mode in THERM_MODES:
            await self.device.home.async_set_thermmode(PRESET_MAP_NETATMO[preset_mode])
        else:
            _LOGGER.error("Preset mode '%s' not available", preset_mode)

        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature for 2 hours."""
        await self.device.async_therm_set(
            STATE_NETATMO_MANUAL, min(kwargs[ATTR_TEMPERATURE], DEFAULT_MAX_TEMP)
        )
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if self.device_type == NA_VALVE:
            await self.device.async_therm_set(
                STATE_NETATMO_MANUAL,
                DEFAULT_MIN_TEMP,
            )
        elif self._attr_hvac_mode != HVACMode.OFF:
            await self.device.async_therm_set(STATE_NETATMO_OFF)
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.device.async_therm_set(STATE_NETATMO_HOME)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """If the device hasn't been able to connect, mark as unavailable."""
        return bool(self._connected)

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self.device.reachable:
            if self.available:
                self._connected = False
            return

        self._connected = True

        self._away_temperature = self.home.get_away_temp()
        self._hg_temperature = self.home.get_hg_temp()
        self._attr_current_temperature = self.device.therm_measured_temperature
        self._attr_target_temperature = self.device.therm_setpoint_temperature
        self._attr_preset_mode = NETATMO_MAP_PRESET[
            getattr(self.device, "therm_setpoint_mode", STATE_NETATMO_SCHEDULE)
        ]
        self._attr_hvac_mode = HVAC_MAP_NETATMO[self._attr_preset_mode]
        self._away = self._attr_hvac_mode == HVAC_MAP_NETATMO[STATE_NETATMO_AWAY]

        self._selected_schedule = getattr(
            self.home.get_selected_schedule(), "name", None
        )
        self._attr_extra_state_attributes[ATTR_SELECTED_SCHEDULE] = (
            self._selected_schedule
        )

        if self.device_type == NA_VALVE:
            self._attr_extra_state_attributes[ATTR_HEATING_POWER_REQUEST] = (
                self.device.heating_power_request
            )
        else:
            for module in self.device.modules.values():
                if hasattr(module, "boiler_status"):
                    module = cast(NATherm1, module)
                    if module.boiler_status is not None:
                        self._boilerstatus = module.boiler_status
                        break

    async def _async_service_set_schedule(self, **kwargs: Any) -> None:
        schedule_name = kwargs.get(ATTR_SCHEDULE_NAME)
        schedule_id = None
        for sid, schedule in self.hass.data[DOMAIN][DATA_SCHEDULES][
            self.home.entity_id
        ].items():
            if schedule.name == schedule_name:
                schedule_id = sid
                break

        if not schedule_id:
            _LOGGER.error("%s is not a valid schedule", kwargs.get(ATTR_SCHEDULE_NAME))
            return

        await self.home.async_switch_schedule(schedule_id=schedule_id)
        _LOGGER.debug(
            "Setting %s schedule to %s (%s)",
            self.home.entity_id,
            kwargs.get(ATTR_SCHEDULE_NAME),
            schedule_id,
        )

    async def _async_service_set_preset_mode_with_end_datetime(
        self, **kwargs: Any
    ) -> None:
        preset_mode = kwargs[ATTR_PRESET_MODE]
        end_datetime = kwargs[ATTR_END_DATETIME]
        end_timestamp = int(dt_util.as_timestamp(end_datetime))

        await self.home.async_set_thermmode(
            mode=PRESET_MAP_NETATMO[preset_mode], end_time=end_timestamp
        )
        _LOGGER.debug(
            "Setting %s preset to %s with end datetime %s",
            self.home.entity_id,
            preset_mode,
            end_timestamp,
        )

    async def _async_service_set_temperature_with_end_datetime(
        self, **kwargs: Any
    ) -> None:
        target_temperature = kwargs[ATTR_TARGET_TEMPERATURE]
        end_datetime = kwargs[ATTR_END_DATETIME]
        end_timestamp = int(dt_util.as_timestamp(end_datetime))

        _LOGGER.debug(
            "Setting %s to target temperature %s with end datetime %s",
            self.device.entity_id,
            target_temperature,
            end_timestamp,
        )
        await self.device.async_therm_manual(target_temperature, end_timestamp)

    async def _async_service_set_temperature_with_time_period(
        self, **kwargs: Any
    ) -> None:
        target_temperature = kwargs[ATTR_TARGET_TEMPERATURE]
        time_period = kwargs[ATTR_TIME_PERIOD]

        _LOGGER.debug(
            "Setting %s to target temperature %s with time period %s",
            self.device.entity_id,
            target_temperature,
            time_period,
        )

        now_timestamp = dt_util.as_timestamp(dt_util.utcnow())
        end_timestamp = int(now_timestamp + time_period.seconds)
        await self.device.async_therm_manual(target_temperature, end_timestamp)

    async def _async_service_clear_temperature_setting(self, **kwargs: Any) -> None:
        _LOGGER.debug("Clearing %s temperature setting", self.device.entity_id)
        await self.device.async_therm_home()
