"""Support for Netatmo Smart thermostats."""
from __future__ import annotations

import logging
from typing import Any, cast

from pyatmo.modules import NATherm1
import voluptuous as vol

from homeassistant.components.climate import (
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
    ATTR_SUGGESTED_AREA,
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    STATE_OFF,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_HEATING_POWER_REQUEST,
    ATTR_SCHEDULE_NAME,
    ATTR_SELECTED_SCHEDULE,
    CONF_URL_ENERGY,
    DATA_SCHEDULES,
    DOMAIN,
    EVENT_TYPE_CANCEL_SET_POINT,
    EVENT_TYPE_SCHEDULE,
    EVENT_TYPE_SET_POINT,
    EVENT_TYPE_THERM_MODE,
    NETATMO_CREATE_CLIMATE,
    SERVICE_SET_SCHEDULE,
)
from .data_handler import HOME, SIGNAL_NAME, NetatmoRoom
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)

PRESET_FROST_GUARD = "Frost Guard"
PRESET_SCHEDULE = "Schedule"
PRESET_MANUAL = "Manual"

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
)
SUPPORT_PRESET = [PRESET_AWAY, PRESET_BOOST, PRESET_FROST_GUARD, PRESET_SCHEDULE]

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

NA_THERM = "NATherm1"
NA_VALVE = "NRV"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo energy platform."""

    @callback
    def _create_entity(netatmo_device: NetatmoRoom) -> None:
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


class NetatmoThermostat(NetatmoBase, ClimateEntity):
    """Representation a Netatmo thermostat."""

    _attr_hvac_mode = HVACMode.AUTO
    _attr_max_temp = DEFAULT_MAX_TEMP
    _attr_preset_modes = SUPPORT_PRESET
    _attr_supported_features = SUPPORT_FLAGS
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, netatmo_device: NetatmoRoom) -> None:
        """Initialize the sensor."""
        ClimateEntity.__init__(self)
        super().__init__(netatmo_device.data_handler)

        self._room = netatmo_device.room
        self._id = self._room.entity_id
        self._home_id = self._room.home.entity_id

        self._signal_name = f"{HOME}-{self._home_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self._room.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._model: str = f"{self._room.climate_type}"

        self._config_url = CONF_URL_ENERGY

        self._attr_name = self._room.name
        self._away: bool | None = None
        self._connected: bool | None = None

        self._away_temperature: float | None = None
        self._hg_temperature: float | None = None
        self._boilerstatus: bool | None = None
        self._selected_schedule = None

        self._attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT]
        if self._model == NA_THERM:
            self._attr_hvac_modes.append(HVACMode.OFF)

        self._attr_unique_id = f"{self._room.entity_id}-{self._model}"

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

        if self._room.home.entity_id != data["home_id"]:
            return

        if data["event_type"] == EVENT_TYPE_SCHEDULE and "schedule_id" in data:
            self._selected_schedule = getattr(
                self.hass.data[DOMAIN][DATA_SCHEDULES][self._room.home.entity_id].get(
                    data["schedule_id"]
                ),
                "name",
                None,
            )
            self._attr_extra_state_attributes[
                ATTR_SELECTED_SCHEDULE
            ] = self._selected_schedule
            self.async_write_ha_state()
            self.data_handler.async_force_update(self._signal_name)
            return

        home = data["home"]

        if self._room.home.entity_id != home["id"]:
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
                and self._room.entity_id == room["id"]
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
                and self._room.entity_id == room["id"]
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
        if self._model != NA_VALVE and self._boilerstatus is not None:
            return CURRENT_HVAC_MAP_NETATMO[self._boilerstatus]
        # Maybe it is a valve
        if (
            heating_req := getattr(self._room, "heating_power_request", 0)
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
            and self._model == NA_VALVE
            and self._attr_hvac_mode == HVACMode.HEAT
        ):
            await self._room.async_therm_set(
                STATE_NETATMO_HOME,
            )
        elif (
            preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX) and self._model == NA_VALVE
        ):
            await self._room.async_therm_set(
                STATE_NETATMO_MANUAL,
                DEFAULT_MAX_TEMP,
            )
        elif (
            preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX)
            and self._attr_hvac_mode == HVACMode.HEAT
        ):
            await self._room.async_therm_set(STATE_NETATMO_HOME)
        elif preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX):
            await self._room.async_therm_set(PRESET_MAP_NETATMO[preset_mode])
        elif preset_mode in (PRESET_SCHEDULE, PRESET_FROST_GUARD, PRESET_AWAY):
            await self._room.home.async_set_thermmode(PRESET_MAP_NETATMO[preset_mode])
        else:
            _LOGGER.error("Preset mode '%s' not available", preset_mode)

        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature for 2 hours."""
        await self._room.async_therm_set(
            STATE_NETATMO_MANUAL, min(kwargs[ATTR_TEMPERATURE], DEFAULT_MAX_TEMP)
        )
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if self._model == NA_VALVE:
            await self._room.async_therm_set(
                STATE_NETATMO_MANUAL,
                DEFAULT_MIN_TEMP,
            )
        elif self._attr_hvac_mode != HVACMode.OFF:
            await self._room.async_therm_set(STATE_NETATMO_OFF)
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self._room.async_therm_set(STATE_NETATMO_HOME)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """If the device hasn't been able to connect, mark as unavailable."""
        return bool(self._connected)

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._room.reachable:
            if self.available:
                self._connected = False
            return

        self._connected = True

        self._away_temperature = self._room.home.get_away_temp()
        self._hg_temperature = self._room.home.get_hg_temp()
        self._attr_current_temperature = self._room.therm_measured_temperature
        self._attr_target_temperature = self._room.therm_setpoint_temperature
        self._attr_preset_mode = NETATMO_MAP_PRESET[
            getattr(self._room, "therm_setpoint_mode", STATE_NETATMO_SCHEDULE)
        ]
        self._attr_hvac_mode = HVAC_MAP_NETATMO[self._attr_preset_mode]
        self._away = self._attr_hvac_mode == HVAC_MAP_NETATMO[STATE_NETATMO_AWAY]

        self._selected_schedule = getattr(
            self._room.home.get_selected_schedule(), "name", None
        )
        self._attr_extra_state_attributes[
            ATTR_SELECTED_SCHEDULE
        ] = self._selected_schedule

        if self._model == NA_VALVE:
            self._attr_extra_state_attributes[
                ATTR_HEATING_POWER_REQUEST
            ] = self._room.heating_power_request
        else:
            for module in self._room.modules.values():
                if hasattr(module, "boiler_status"):
                    module = cast(NATherm1, module)
                    if module.boiler_status is not None:
                        self._boilerstatus = module.boiler_status
                        break

    async def _async_service_set_schedule(self, **kwargs: Any) -> None:
        schedule_name = kwargs.get(ATTR_SCHEDULE_NAME)
        schedule_id = None
        for sid, schedule in self.hass.data[DOMAIN][DATA_SCHEDULES][
            self._room.home.entity_id
        ].items():
            if schedule.name == schedule_name:
                schedule_id = sid
                break

        if not schedule_id:
            _LOGGER.error("%s is not a valid schedule", kwargs.get(ATTR_SCHEDULE_NAME))
            return

        await self._room.home.async_switch_schedule(schedule_id=schedule_id)
        _LOGGER.debug(
            "Setting %s schedule to %s (%s)",
            self._room.home.entity_id,
            kwargs.get(ATTR_SCHEDULE_NAME),
            schedule_id,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for the thermostat."""
        device_info: DeviceInfo = super().device_info
        device_info[ATTR_SUGGESTED_AREA] = self._room.name
        return device_info
