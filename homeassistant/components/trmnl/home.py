"""Send a snapshot of the home to a TRMNL plugin setting."""

from collections.abc import Callable
from datetime import datetime, timedelta
import json
from typing import Any

from trmnl.exceptions import TRMNLError, TRMNLForbiddenError

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
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
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .const import LOGGER

PUSH_INTERVAL = timedelta(minutes=5)
CHANGE_PUSH_COOLDOWN_SECONDS = 60

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
                "name": (device.name_by_user or device.name) if device else state.name,
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
    """Push the picked entities on a timer and soon after they change, skipping unchanged pushes."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_ids: list[str],
        push: Callable[[dict[str, Any]], Any],
    ) -> None:
        """Initialize the pusher."""
        self._hass = hass
        self._entity_ids = entity_ids
        self._push = push
        self._last_body: str | None = None
        self._debouncer = Debouncer(
            hass,
            LOGGER,
            cooldown=CHANGE_PUSH_COOLDOWN_SECONDS,
            immediate=False,
            function=self.async_push,
        )

    async def async_push(self) -> None:
        """Push the snapshot if it changed since the last push."""
        snapshot = build_snapshot(self._hass, self._entity_ids)
        body = json.dumps(snapshot, sort_keys=True)
        if body == self._last_body:
            return
        try:
            await self._push(snapshot)
        except TRMNLForbiddenError as err:
            LOGGER.warning(
                'TRMNL refused the home: %s. Sign in again with "Change your markup,'
                ' plugin settings, playlists and mashups" ticked',
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
            self._hass, self._async_timer_push, PUSH_INTERVAL
        )
        cancel_listener = async_track_state_change_event(
            self._hass, self._entity_ids, self._async_state_changed
        )
        self._hass.async_create_task(self.async_push())

        @callback
        def stop() -> None:
            cancel_timer()
            cancel_listener()
            self._debouncer.async_cancel()

        return stop

    async def _async_timer_push(self, _now: datetime) -> None:
        await self.async_push()

    @callback
    def _async_state_changed(self, _event: Event[EventStateChangedData]) -> None:
        self._hass.async_create_task(self._debouncer.async_call())
