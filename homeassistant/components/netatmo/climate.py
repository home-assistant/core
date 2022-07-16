"""Support for Netatmo Smart thermostats."""
from __future__ import annotations

import logging
from typing import Any

import pyatmo
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    DEFAULT_MIN_TEMP,
    PRESET_AWAY,
    PRESET_BOOST,
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
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_HEATING_POWER_REQUEST,
    ATTR_SCHEDULE_NAME,
    ATTR_SELECTED_SCHEDULE,
    DATA_HANDLER,
    DATA_HOMES,
    DATA_SCHEDULES,
    DOMAIN,
    EVENT_TYPE_CANCEL_SET_POINT,
    EVENT_TYPE_SCHEDULE,
    EVENT_TYPE_SET_POINT,
    EVENT_TYPE_THERM_MODE,
    NETATMO_CREATE_BATTERY,
    SERVICE_SET_SCHEDULE,
    SIGNAL_NAME,
    TYPE_ENERGY,
)
from .data_handler import (
    CLIMATE_STATE_CLASS_NAME,
    CLIMATE_TOPOLOGY_CLASS_NAME,
    NetatmoDataHandler,
    NetatmoDevice,
)
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)

PRESET_FROST_GUARD = "Frost Guard"
PRESET_SCHEDULE = "Schedule"
PRESET_MANUAL = "Manual"

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
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    climate_topology = data_handler.data.get(CLIMATE_TOPOLOGY_CLASS_NAME)

    if not climate_topology or climate_topology.raw_data == {}:
        raise PlatformNotReady

    entities = []
    for home_id in climate_topology.home_ids:
        signal_name = f"{CLIMATE_STATE_CLASS_NAME}-{home_id}"

        await data_handler.subscribe(
            CLIMATE_STATE_CLASS_NAME, signal_name, None, home_id=home_id
        )

        if (climate_state := data_handler.data[signal_name]) is None:
            continue

        climate_topology.register_handler(home_id, climate_state.process_topology)

        for room in climate_state.homes[home_id].rooms.values():
            if room.device_type is None or room.device_type.value not in [
                NA_THERM,
                NA_VALVE,
            ]:
                continue
            entities.append(NetatmoThermostat(data_handler, room))

        hass.data[DOMAIN][DATA_SCHEDULES][home_id] = climate_state.homes[
            home_id
        ].schedules

        hass.data[DOMAIN][DATA_HOMES][home_id] = climate_state.homes[home_id].name

    _LOGGER.debug("Adding climate devices %s", entities)
    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()

    if climate_topology is not None:
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
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(
        self, data_handler: NetatmoDataHandler, room: pyatmo.climate.NetatmoRoom
    ) -> None:
        """Initialize the sensor."""
        ClimateEntity.__init__(self)
        super().__init__(data_handler)

        self._room = room
        self._id = self._room.entity_id

        self._signal_name = f"{CLIMATE_STATE_CLASS_NAME}-{self._room.home.entity_id}"
        self._climate_state: pyatmo.AsyncClimate = data_handler.data[self._signal_name]

        self._publishers.extend(
            [
                {
                    "name": CLIMATE_TOPOLOGY_CLASS_NAME,
                    SIGNAL_NAME: CLIMATE_TOPOLOGY_CLASS_NAME,
                },
                {
                    "name": CLIMATE_STATE_CLASS_NAME,
                    "home_id": self._room.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._model: str = getattr(room.device_type, "value")

        self._netatmo_type = TYPE_ENERGY

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
            self.data_handler.config_entry.async_on_unload(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{event_type}",
                    self.handle_event,
                )
            )

        for module in self._room.modules.values():
            if getattr(module.device_type, "value") not in [NA_THERM, NA_VALVE]:
                continue

            async_dispatcher_send(
                self.hass,
                NETATMO_CREATE_BATTERY,
                NetatmoDevice(
                    self.data_handler,
                    module,
                    self._id,
                    self._signal_name,
                ),
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
            elif self._attr_preset_mode == PRESET_SCHEDULE:
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
                self.async_update_callback()
                self.async_write_ha_state()
                return

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported."""
        if self._model == NA_THERM and self._boilerstatus is not None:
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
            if self.hvac_mode == HVACMode.OFF:
                await self.async_turn_on()
            await self.async_set_preset_mode(PRESET_SCHEDULE)
        elif hvac_mode == HVACMode.HEAT:
            await self.async_set_preset_mode(PRESET_BOOST)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.hvac_mode == HVACMode.OFF:
            await self.async_turn_on()

        if self.target_temperature == 0:
            await self._climate_state.async_set_room_thermpoint(
                self._room.entity_id,
                STATE_NETATMO_HOME,
            )

        if (
            preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX)
            and self._model == NA_VALVE
            and self.hvac_mode == HVACMode.HEAT
        ):
            await self._climate_state.async_set_room_thermpoint(
                self._room.entity_id,
                STATE_NETATMO_HOME,
            )
        elif (
            preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX) and self._model == NA_VALVE
        ):
            await self._climate_state.async_set_room_thermpoint(
                self._room.entity_id,
                STATE_NETATMO_MANUAL,
                DEFAULT_MAX_TEMP,
            )
        elif (
            preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX)
            and self.hvac_mode == HVACMode.HEAT
        ):
            await self._climate_state.async_set_room_thermpoint(
                self._room.entity_id, STATE_NETATMO_HOME
            )
        elif preset_mode in (PRESET_BOOST, STATE_NETATMO_MAX):
            await self._climate_state.async_set_room_thermpoint(
                self._room.entity_id, PRESET_MAP_NETATMO[preset_mode]
            )
        elif preset_mode in (PRESET_SCHEDULE, PRESET_FROST_GUARD, PRESET_AWAY):
            await self._climate_state.async_set_thermmode(
                PRESET_MAP_NETATMO[preset_mode]
            )
        else:
            _LOGGER.error("Preset mode '%s' not available", preset_mode)

        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature for 2 hours."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._climate_state.async_set_room_thermpoint(
            self._room.entity_id, STATE_NETATMO_MANUAL, min(temp, DEFAULT_MAX_TEMP)
        )

        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if self._model == NA_VALVE:
            await self._climate_state.async_set_room_thermpoint(
                self._room.entity_id,
                STATE_NETATMO_MANUAL,
                DEFAULT_MIN_TEMP,
            )
        elif self.hvac_mode != HVACMode.OFF:
            await self._climate_state.async_set_room_thermpoint(
                self._room.entity_id, STATE_NETATMO_OFF
            )
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self._climate_state.async_set_room_thermpoint(
            self._room.entity_id, STATE_NETATMO_HOME
        )
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

        await self._climate_state.async_switch_home_schedule(schedule_id=schedule_id)
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
