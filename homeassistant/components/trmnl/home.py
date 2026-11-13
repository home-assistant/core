"""Send a snapshot of the home to a TRMNL plugin setting."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
import json
from typing import Any

from trmnl.exceptions import TRMNLError, TRMNLForbiddenError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)

from .const import LOGGER

PUSH_INTERVAL = timedelta(minutes=5)
PUSH_COOLDOWN_SECONDS = 60

SENSOR_CAPABILITIES = {
    "temperature": "measure_temperature",
    "humidity": "measure_humidity",
    "power": "measure_power",
    "energy": "meter_power",
    "battery": "measure_battery",
    "carbon_dioxide": "measure_co2",
    "carbon_monoxide": "measure_co",
    "pm25": "measure_pm25",
    "illuminance": "measure_luminance",
    "pressure": "measure_pressure",
    "atmospheric_pressure": "measure_pressure",
    "gas": "meter_gas",
    "water": "meter_water",
    "voltage": "measure_voltage",
    "current": "measure_current",
    "sound_pressure": "measure_noise",
    "wind_speed": "measure_wind_strength",
}
BINARY_SENSOR_CAPABILITIES = {
    "motion": "alarm_motion",
    "occupancy": "alarm_motion",
    "presence": "alarm_motion",
    "door": "alarm_contact",
    "window": "alarm_contact",
    "opening": "alarm_contact",
    "garage_door": "alarm_contact",
    "moisture": "alarm_water",
    "smoke": "alarm_smoke",
    "carbon_monoxide": "alarm_co",
    "battery": "alarm_battery",
    "tamper": "alarm_tamper",
    "heat": "alarm_heat",
    "gas": "alarm_gas",
}
DEVICE_CLASS_BY_DOMAIN = {
    "light": "light",
    "switch": "socket",
    "climate": "thermostat",
    "lock": "lock",
    "cover": "windowcoverings",
    "fan": "fan",
    "media_player": "speaker",
    "vacuum": "vacuumcleaner",
    "alarm_control_panel": "homealarm",
    "water_heater": "heater",
    "humidifier": "other",
    "sensor": "sensor",
    "binary_sensor": "sensor",
}
THERMOSTAT_MODES = {"auto", "cool", "heat", "off"}
ALARM_STATES = {
    "disarmed": "disarmed",
    "armed_home": "partially_armed",
    "armed_night": "partially_armed",
}


def _number(value: Any) -> float | int | None:
    """Return a number, as an int when it has no fraction."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    return int(number) if number.is_integer() else number


def _onoff(state: State) -> dict[str, dict[str, Any]]:
    capabilities = {"onoff": {"value": state.state == STATE_ON}}
    if (brightness := state.attributes.get("brightness")) is not None:
        capabilities["dim"] = {"value": round(brightness / 255, 2)}
    return capabilities


def _climate(state: State) -> dict[str, dict[str, Any]]:
    capabilities: dict[str, dict[str, Any]] = {}
    if (current := _number(state.attributes.get("current_temperature"))) is not None:
        capabilities["measure_temperature"] = {"value": current}
    if (target := _number(state.attributes.get("temperature"))) is not None:
        capabilities["target_temperature"] = {"value": target}
    if state.state in THERMOSTAT_MODES:
        capabilities["thermostat_mode"] = {"value": state.state}
    return capabilities


def _cover(state: State) -> dict[str, dict[str, Any]]:
    if state.attributes.get("device_class") == "garage":
        return {"garagedoor_closed": {"value": state.state == "closed"}}
    if (position := state.attributes.get("current_position")) is not None:
        return {"windowcoverings_set": {"value": position / 100}}
    return {}


def _sensor(state: State) -> dict[str, dict[str, Any]]:
    capability = SENSOR_CAPABILITIES.get(state.attributes.get("device_class", ""))
    if capability is None or (value := _number(state.state)) is None:
        return {}
    unit = state.attributes.get("unit_of_measurement")
    return {capability: {"value": value} | ({"units": unit} if unit else {})}


def _binary_sensor(state: State) -> dict[str, dict[str, Any]]:
    capability = BINARY_SENSOR_CAPABILITIES.get(
        state.attributes.get("device_class", "")
    )
    return {capability: {"value": state.state == STATE_ON}} if capability else {}


CAPABILITIES_BY_DOMAIN: dict[str, Callable[[State], dict[str, dict[str, Any]]]] = {
    "sensor": _sensor,
    "binary_sensor": _binary_sensor,
    "light": _onoff,
    "switch": _onoff,
    "fan": _onoff,
    "humidifier": _onoff,
    "climate": _climate,
    "cover": _cover,
    "lock": lambda state: {"locked": {"value": state.state == "locked"}},
    "media_player": lambda state: {
        "speaker_playing": {"value": state.state == "playing"}
    },
    "alarm_control_panel": lambda state: {
        "homealarm_state": {"value": ALARM_STATES.get(state.state, "armed")}
    },
}


def capabilities_of(state: State) -> dict[str, dict[str, Any]]:
    """Return the TRMNL capabilities one entity state maps to."""
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return {}
    mapper = CAPABILITIES_BY_DOMAIN.get(state.domain)
    return mapper(state) if mapper else {}


def build_snapshot(hass: HomeAssistant, entity_ids: list[str]) -> dict[str, Any]:
    """Return the picked entities in the wire shape TRMNL's Homey recipes read."""
    area_names = {area.id: area.name for area in ar.async_get(hass).async_list_areas()}
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    grouped: dict[str, dict[str, Any]] = {}
    used_area_names: dict[str, str] = {}
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None or not (capabilities := capabilities_of(state)):
            continue
        entry = entities.async_get(entity_id)
        device = (
            devices.async_get(entry.device_id) if entry and entry.device_id else None
        )
        area_id = (entry.area_id if entry else None) or (
            device.area_id if device else None
        )
        if area_id and area_id in area_names:
            used_area_names[area_id] = area_names[area_id]
        record = grouped.setdefault(
            device.id if device else state.entity_id,
            {
                "name": (device and (device.name_by_user or device.name)) or state.name,
                "zone": area_names.get(area_id or "", "Unzoned"),
                "domains": [],
                "available": True,
                "capabilities": {},
            },
        )
        record["domains"].append(state.domain)
        for capability_id, capability in capabilities.items():
            key, suffix = capability_id, 1
            while key in record["capabilities"]:
                suffix += 1
                key = f"{capability_id}.{suffix}"
            record["capabilities"][key] = capability
    for record in grouped.values():
        domains = record.pop("domains")
        record["klass"] = next(
            (
                klass
                for domain, klass in DEVICE_CLASS_BY_DOMAIN.items()
                if domain in domains
            ),
            "other",
        )
    return {
        "source": "home_assistant",
        "zone_names": used_area_names,
        "devices": list(grouped.values()),
    }


class HomePusher:
    """Push the picked entities on start, on a timer and after they change.

    All three share one cooldown, so TRMNL gets at most one push a minute.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        entity_ids: list[str],
        push: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Initialize the pusher."""
        self._hass = hass
        self._entry = entry
        self._entity_ids = entity_ids
        self._push = push
        self._lock = asyncio.Lock()
        self._last_body: str | None = None
        self._cancel_cooldown: CALLBACK_TYPE | None = None
        self._push_pending = False
        # Set when TRMNL refuses for a missing scope; the reauth reload makes a new pusher.
        self._refused_for_scope = False

    @callback
    def async_request_push(self) -> None:
        """Push now, or when the cooldown ends; requests made meanwhile share that push."""
        if self._refused_for_scope:
            return
        if self._cancel_cooldown is not None:
            self._push_pending = True
            return
        self._push_pending = False
        self._cancel_cooldown = async_call_later(
            self._hass, PUSH_COOLDOWN_SECONDS, self._async_cooldown_ended
        )
        # An entry task, so unloading the entry waits for a push that is under way.
        self._entry.async_create_task(self._hass, self._async_push(), "trmnl_home_push")

    @callback
    def _async_cooldown_ended(self, _now: datetime) -> None:
        self._cancel_cooldown = None
        if self._push_pending:
            self.async_request_push()

    async def _async_push(self) -> None:
        """Push the snapshot if it changed since the last push."""
        async with self._lock:
            snapshot = build_snapshot(self._hass, self._entity_ids)
            body = json.dumps(snapshot, sort_keys=True)
            if body == self._last_body:
                return
            try:
                await self._push(snapshot)
            except TRMNLForbiddenError as err:
                self._refused_for_scope = True
                self._entry.async_start_reauth(self._hass)
                LOGGER.warning(
                    'TRMNL refused the home: %s. Sign in again with "Change your'
                    ' markup, plugin settings, playlists and mashups" ticked',
                    err,
                )
                return
            except TRMNLError as err:
                LOGGER.warning("Could not send the home to TRMNL: %s", err)
                return
            self._last_body = body
            LOGGER.debug("Pushed %s devices to TRMNL", len(snapshot["devices"]))

    @callback
    def async_start(self) -> Callable[[], None]:
        """Start pushing; return a callback that stops."""
        cancel_timer = async_track_time_interval(
            self._hass, self._async_timer_fired, PUSH_INTERVAL
        )
        cancel_listener = async_track_state_change_event(
            self._hass, self._entity_ids, self._async_state_changed
        )
        self.async_request_push()

        @callback
        def stop() -> None:
            cancel_timer()
            cancel_listener()
            if self._cancel_cooldown is not None:
                self._cancel_cooldown()

        return stop

    @callback
    def _async_timer_fired(self, _now: datetime) -> None:
        self.async_request_push()

    @callback
    def _async_state_changed(self, _event: Event[EventStateChangedData]) -> None:
        self.async_request_push()
