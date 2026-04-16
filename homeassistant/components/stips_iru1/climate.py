"""Climate platform for STIPS IRU1 protocol AC remotes."""

from __future__ import annotations

from typing import Any

import aiohttp
from yarl import URL

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import (
    model_has_ir_signals,
    normalize_device_ip,
    normalize_device_mac,
    normalize_device_online,
)
from .const import DOMAIN, is_learned_ac, is_protocol_ac
from .local_http import _local_http_auth, async_build_control_hosts

_MODE_TO_HVAC: dict[int, HVACMode] = {
    0: HVACMode.AUTO,
    1: HVACMode.COOL,
    2: HVACMode.HEAT,
    3: HVACMode.DRY,
    4: HVACMode.FAN_ONLY,
}
_HVAC_TO_MODE: dict[HVACMode, int] = {v: k for k, v in _MODE_TO_HVAC.items()}

_FAN_INT_TO_NAME: dict[int, str] = {
    0: "auto",
    1: "min",
    2: "low",
    3: "medium",
    4: "high",
    5: "max",
}
_FAN_NAME_TO_INT: dict[str, int] = {v: k for k, v in _FAN_INT_TO_NAME.items()}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except TypeError:
        return default
    except ValueError:
        return default


def _normalize_swing_mode(swing_v: int, swing_h: int) -> str:
    if swing_v and swing_h:
        return "both"
    if swing_v:
        return "vertical"
    if swing_h:
        return "horizontal"
    return "off"


def _split_swing_mode(mode: str) -> tuple[int, int]:
    m = (mode or "").strip().lower()
    if m == "vertical":
        return 1, 0
    if m == "horizontal":
        return 0, 1
    if m == "both":
        return 1, 1
    return 0, 0


def _normalize_mode_label(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in {"fan", "fan_only", "fanonly"}:
        return "fan"
    return s


def _mode_to_hvac(mode: Any) -> HVACMode:
    m = _normalize_mode_label(mode)
    if m == "auto":
        return HVACMode.AUTO
    if m == "cool":
        return HVACMode.COOL
    if m == "heat":
        return HVACMode.HEAT
    if m == "dry":
        return HVACMode.DRY
    if m == "fan":
        return HVACMode.FAN_ONLY
    return HVACMode.COOL


def _fan_to_name(value: Any) -> str:
    v = str(value or "").strip().lower()
    if v in _FAN_NAME_TO_INT:
        return v
    if v.isdigit():
        return _FAN_INT_TO_NAME.get(int(v), "medium")
    aliases = {
        "med": "medium",
        "mid": "medium",
        "maximum": "max",
        "minimum": "min",
    }
    return aliases.get(v, "medium")


def _extract_learned_ac_signals(
    remote_snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None, str | None, int]:
    model = remote_snapshot.get("model") or {}
    frequency = _safe_int(model.get("frequency") or model.get("Frequency"), 38000)
    out: list[dict[str, Any]] = []
    for raw in model.get("signals") or model.get("Signals") or []:
        if not isinstance(raw, dict):
            continue
        signal = raw.get("signal") or raw.get("Signal")
        if not signal or not str(signal).strip():
            continue
        mode = _normalize_mode_label(raw.get("mode") or "")
        temp: int | None = None
        temperature = raw.get("temperature")
        if temperature is not None:
            try:
                temp = int(temperature)
            except TypeError:
                temp = None
            except ValueError:
                temp = None
        fan = _fan_to_name(raw.get("fanSpeed") or raw.get("fan") or "")
        out.append(
            {
                "mode": mode,
                "temp": temp,
                "fan": fan,
                "signal": str(signal),
            }
        )
    power_on = model.get("powerOnSignal") or model.get("PowerOnSignal")
    power_off = model.get("powerOffSignal") or model.get("PowerOffSignal")
    on_s = (
        str(power_on).strip()
        if power_on is not None and str(power_on).strip()
        else None
    )
    off_s = (
        str(power_off).strip()
        if power_off is not None and str(power_off).strip()
        else None
    )
    return out, on_s, off_s, frequency


def _pick_best_learned_signal(
    entries: list[dict[str, Any]],
    hvac_mode: HVACMode,
    temp: int,
    fan_mode: str,
) -> str | None:
    wanted_mode = "fan" if hvac_mode == HVACMode.FAN_ONLY else hvac_mode.value
    wanted_mode = _normalize_mode_label(wanted_mode)
    wanted_fan = _fan_to_name(fan_mode)

    best: tuple[int, str] | None = None
    for row in entries:
        row_mode = _normalize_mode_label(row.get("mode"))
        row_temp = row.get("temp")
        row_fan = _fan_to_name(row.get("fan"))
        if row_mode and row_mode != wanted_mode:
            continue
        score = 0
        if row_mode == wanted_mode:
            score += 4
        if row_temp is not None:
            try:
                row_temp_int = int(row_temp)
            except TypeError:
                continue
            except ValueError:
                continue
            if row_temp_int != temp:
                continue
            score += 2
        if row_fan and row_fan != wanted_fan:
            continue
        if row_fan == wanted_fan:
            score += 1
        sig = str(row.get("signal") or "").strip()
        if not sig:
            continue
        if best is None or score > best[0]:
            best = (score, sig)
    return best[1] if best is not None else None


def _extract_initial_ac_state(remote: dict[str, Any]) -> dict[str, int]:
    ac = remote.get("acStatus") or {}
    modes = ac.get("modeStates") or {}
    last_key = str(ac.get("lastModeName") or "cool").strip().lower()
    chosen: dict[str, Any] | None = None

    if isinstance(modes, dict):
        for key, state in modes.items():
            if str(key).strip().lower() == last_key and isinstance(state, dict):
                chosen = state
                break
        if chosen is None:
            for state in modes.values():
                if isinstance(state, dict):
                    chosen = state
                    break

    if chosen is None:
        chosen = {}

    return {
        "power": _safe_int(chosen.get("power"), 0),
        "mode": _safe_int(chosen.get("mode"), 1),
        "fan": _safe_int(chosen.get("fan"), 3),
        "temp": _safe_int(chosen.get("temperature"), 22),
        "swingV": _safe_int(chosen.get("swingV"), 0),
        "swingH": _safe_int(chosen.get("swingH"), 0),
        "light": _safe_int(chosen.get("light"), 1),
        "beep": _safe_int(chosen.get("beep"), 1),
        "econo": _safe_int(chosen.get("econo"), 0),
        "filter": _safe_int(chosen.get("filter"), 0),
        "turbo": _safe_int(chosen.get("turbo"), 0),
        "quiet": _safe_int(chosen.get("quiet"), 0),
        "clean": _safe_int(chosen.get("clean"), 0),
        "sleep": _safe_int(chosen.get("sleep"), 0),
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create climate entities for protocol AC and LearnedAc remotes."""
    entities: list[ClimateEntity] = []

    for device in entry.runtime_data.devices:
        device_unique_name = device.get("uniqueName")
        if not device_unique_name:
            continue
        device_name = device.get("name") or device_unique_name
        device_ip = normalize_device_ip(device)
        device_mac = normalize_device_mac(device)
        device_online = normalize_device_online(device)
        remotes = device.get("remotes") or []

        for idx, remote in enumerate(remotes):
            remote_type = str(remote.get("type") or "")
            model = remote.get("model") or {}

            remote_id = remote.get("id")
            friendly = remote.get("friendlyName") or remote.get("type") or "AC"
            rid = (
                str(remote_id)
                if remote_id is not None
                else f"{idx}_{str(friendly).strip().lower().replace(' ', '_')}"
            )

            if is_protocol_ac(remote_type):
                if model.get("protocol") is None:
                    continue
                entities.append(
                    StipsIruClimate(
                        hass=hass,
                        device_unique_name=str(device_unique_name),
                        device_name=str(device_name),
                        device_ip=device_ip,
                        device_mac=device_mac,
                        device_online=device_online,
                        remote_id=str(rid),
                        friendly_name=str(friendly),
                        remote_snapshot=dict(remote),
                    )
                )
                continue

            if is_learned_ac(remote_type) and model_has_ir_signals(model):
                entities.append(
                    StipsIruLearnedAcClimate(
                        hass=hass,
                        device_unique_name=str(device_unique_name),
                        device_name=str(device_name),
                        device_ip=device_ip,
                        device_mac=device_mac,
                        device_online=device_online,
                        remote_id=str(rid),
                        friendly_name=str(friendly),
                        remote_snapshot=dict(remote),
                    )
                )

    async_add_entities(entities)


class StipsIruClimate(ClimateEntity):
    """Climate control for one STIPS protocol AC remote."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_icon = "mdi:air-conditioner"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = ["auto", "min", "low", "medium", "high", "max"]
    _attr_swing_modes = ["off", "vertical", "horizontal", "both"]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        device_unique_name: str,
        device_name: str,
        device_ip: str,
        device_mac: str,
        device_online: bool,
        remote_id: str,
        friendly_name: str,
        remote_snapshot: dict[str, Any],
    ) -> None:
        """Initialize a protocol AC climate entity."""
        super().__init__()
        self.hass = hass
        self._device_unique_name = device_unique_name
        self._device_name = device_name
        self._device_ip = device_ip
        self._device_ip_live = ""
        self._device_mac = device_mac
        self._device_online = device_online
        self._remote_snapshot = remote_snapshot
        self._proto = _safe_int(
            (remote_snapshot.get("model") or {}).get("protocol"), -1
        )
        self._model = 0
        self._control_hosts_cache: list[str] | None = None
        self._control_live_ip_cache: str | None = None

        safe_rid = "".join(c if c.isalnum() or c in "-_" else "_" for c in remote_id)[
            :80
        ]
        self._attr_unique_id = f"{DOMAIN}_{device_unique_name}_climate_{safe_rid}"
        self._attr_name = f"{friendly_name} Climate"
        self._attr_available = bool(device_online)

        self._state = _extract_initial_ac_state(remote_snapshot)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device registry metadata for this climate entity."""
        device_info: dict[str, Any] = {
            "identifiers": {(DOMAIN, self._device_unique_name)},
            "name": self._device_name,
            "manufacturer": "STIPS",
            "model": "IRU1",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._device_mac)}
            if self._device_mac
            else set(),
        }

        device_host = str(getattr(self, "_device_ip", "") or "").strip()
        if device_host:
            try:
                device_info["configuration_url"] = str(
                    URL.build(scheme="http", host=device_host, path="/device_info")
                )
            except ValueError:
                pass

        return DeviceInfo(**device_info)
    @property
    def available(self) -> bool:
        """Return latest known availability state for this remote."""
        return bool(self._attr_available)

    @property
    def hvac_mode(self) -> HVACMode:
        """Current HVAC mode derived from the last known AC state."""
        if _safe_int(self._state.get("power"), 0) == 0:
            return HVACMode.OFF
        return _MODE_TO_HVAC.get(_safe_int(self._state.get("mode"), 1), HVACMode.COOL)

    @property
    def target_temperature(self) -> float:
        """Current target temperature in Celsius."""
        return float(_safe_int(self._state.get("temp"), 22))

    @property
    def fan_mode(self) -> str:
        """Current fan mode label."""
        return _FAN_INT_TO_NAME.get(_safe_int(self._state.get("fan"), 3), "medium")

    @property
    def swing_mode(self) -> str:
        """Current swing mode label."""
        return _normalize_swing_mode(
            _safe_int(self._state.get("swingV"), 0),
            _safe_int(self._state.get("swingH"), 0),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose non-sensitive metadata for the backing STIPS device."""
        return {
            "device_unique_name": self._device_unique_name,
            "unique_name": self._device_unique_name,
            "device_online": self._device_online,
            "remote_type": self._remote_snapshot.get("type"),
            "protocol": self._proto,
            "light": _safe_int(self._state.get("light"), 1),
            "beep": _safe_int(self._state.get("beep"), 1),
            "econo": _safe_int(self._state.get("econo"), 0),
            "filter": _safe_int(self._state.get("filter"), 0),
            "turbo": _safe_int(self._state.get("turbo"), 0),
            "quiet": _safe_int(self._state.get("quiet"), 0),
            "clean": _safe_int(self._state.get("clean"), 0),
            "sleep": _safe_int(self._state.get("sleep"), 0),
        }

    async def async_turn_on(self) -> None:
        """Turn the AC on using the cached protocol state."""
        await self._send_update(power=1)

    async def async_turn_off(self) -> None:
        """Turn the AC off using the cached protocol state."""
        await self._send_update(power=0)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Apply a new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._send_update(power=0)
            return
        mode = _HVAC_TO_MODE.get(hvac_mode)
        if mode is None:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        await self._send_update(power=1, mode=mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Apply a new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            raise HomeAssistantError("Temperature is required")
        requested = int(float(kwargs[ATTR_TEMPERATURE]))
        requested = max(int(self.min_temp), min(int(self.max_temp), requested))
        await self._send_update(power=1, temp=requested)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Apply a new fan mode."""
        key = (fan_mode or "").strip().lower()
        if key not in _FAN_NAME_TO_INT:
            raise HomeAssistantError(f"Unsupported fan mode: {fan_mode}")
        await self._send_update(power=1, fan=_FAN_NAME_TO_INT[key])

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Apply a new swing mode."""
        swing_v, swing_h = _split_swing_mode(swing_mode)
        await self._send_update(power=1, swingV=swing_v, swingH=swing_h)

    def _get_cached_control_hosts(self) -> tuple[list[str], str | None]:
        """Return cached control hosts and live IP if available."""
        hosts = getattr(self, "_control_hosts_cache", None)
        live_ip = getattr(self, "_control_live_ip_cache", None)
        if not hosts:
            return [], None
        return list(hosts), live_ip

    async def async_resolve_control_hosts(
        self, *, force_refresh: bool = False
    ) -> tuple[list[str], str | None]:
        """Resolve control hosts, reusing a cached result when possible."""
        if not force_refresh:
            cached_hosts, cached_live_ip = self._get_cached_control_hosts()
            if cached_hosts:
                return cached_hosts, cached_live_ip

        hosts, live_ip = await async_build_control_hosts(
            self.hass,
            device_unique_name=self._device_unique_name,
            backend_ip=self._device_ip,
        )
        if hosts:
            self._control_hosts_cache = list(hosts)
            self._control_live_ip_cache = live_ip
        return hosts, live_ip

    async def _send_update(self, **overrides: int) -> None:
        hosts, live_ip = await self.async_resolve_control_hosts()
        if not hosts:
            raise HomeAssistantError(
                "Device host is missing; verify the IRU is online and its mDNS name resolves, "
                "then reload or reconfigure the integration."
            )
        if live_ip:
            self._device_ip_live = live_ip
        if self._proto < 0:
            raise HomeAssistantError("AC protocol is missing in remote model")

        payload_state = dict(self._state)
        payload_state.update(overrides)

        fields: dict[str, Any] = {
            "type": self._proto,
            "model": self._model,
            "power": _safe_int(payload_state.get("power"), 0),
            "mode": _safe_int(payload_state.get("mode"), 1),
            "fan": _safe_int(payload_state.get("fan"), 3),
            "temp": _safe_int(payload_state.get("temp"), 22),
            "swingV": _safe_int(payload_state.get("swingV"), 0),
            "swingH": _safe_int(payload_state.get("swingH"), 0),
            "light": _safe_int(payload_state.get("light"), 1),
            "beep": _safe_int(payload_state.get("beep"), 1),
            "econo": _safe_int(payload_state.get("econo"), 0),
            "filter": _safe_int(payload_state.get("filter"), 0),
            "turbo": _safe_int(payload_state.get("turbo"), 0),
            "quiet": _safe_int(payload_state.get("quiet"), 0),
            "clean": _safe_int(payload_state.get("clean"), 0),
            "sleep": _safe_int(payload_state.get("sleep"), 0),
        }

        session = async_get_clientsession(self.hass)
        auth = _local_http_auth()
        timeout = aiohttp.ClientTimeout(
            total=3, connect=1.5, sock_connect=1.5, sock_read=2
        )
        last_error: Exception | None = None
        sent_ok = False
        for host in hosts:
            url = str(URL.build(scheme="http", host=host, path="/local-ir/ac-command"))
            try:
                async with session.post(
                    url,
                    data={k: str(v) for k, v in fields.items()},
                    auth=auth,
                    timeout=timeout,
                ) as response:
                    if response.status >= 400:
                        body = await response.text()
                        last_error = HomeAssistantError(
                            f"Local AC request failed ({response.status}) via {host}: {body[:160]}"
                        )
                        continue
                    sent_ok = True
                    self._attr_available = True
                    last_error = None
                    break
            except (TimeoutError, aiohttp.ClientError) as err:
                last_error = err
                continue
        if not sent_ok and isinstance(last_error, HomeAssistantError):
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"{last_error} | hosts={', '.join(hosts)}")
        if not sent_ok and last_error is not None:
            self._attr_available = False
            self.async_write_ha_state()
            detail = str(last_error).strip() or type(last_error).__name__
            raise HomeAssistantError(
                f"Cannot reach IR device locally (hosts: {', '.join(hosts)}): {detail}"
            ) from last_error
        if not sent_ok:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Cannot reach IR device locally (hosts: {', '.join(hosts)})"
            )

        self._state = payload_state
        self.async_write_ha_state()


class StipsIruLearnedAcClimate(ClimateEntity):
    """Climate control for LearnedAc remotes using learned signal rows."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_icon = "mdi:air-conditioner"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = ["auto", "min", "low", "medium", "high", "max"]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        device_unique_name: str,
        device_name: str,
        device_ip: str,
        device_mac: str,
        device_online: bool,
        remote_id: str,
        friendly_name: str,
        remote_snapshot: dict[str, Any],
    ) -> None:
        """Initialize a learned-AC climate entity."""
        super().__init__()
        self.hass = hass
        self._device_unique_name = device_unique_name
        self._device_name = device_name
        self._device_ip = device_ip
        self._device_ip_live = ""
        self._device_mac = device_mac
        self._device_online = device_online
        self._remote_snapshot = remote_snapshot
        self._remote_type = str(remote_snapshot.get("type") or "LearnedAc")

        (
            self._signals,
            self._power_on_signal,
            self._power_off_signal,
            self._frequency,
        ) = _extract_learned_ac_signals(remote_snapshot)
        temps = [int(v["temp"]) for v in self._signals if v.get("temp") is not None]
        self._attr_min_temp = min(temps) if temps else 16
        self._attr_max_temp = max(temps) if temps else 30

        safe_rid = "".join(c if c.isalnum() or c in "-_" else "_" for c in remote_id)[
            :80
        ]
        self._attr_unique_id = (
            f"{DOMAIN}_{device_unique_name}_climate_learned_ac_{safe_rid}"
        )
        self._attr_available = bool(device_online)

        modes = {_mode_to_hvac(v.get("mode")) for v in self._signals}
        self._attr_hvac_modes = [
            HVACMode.OFF,
            *[
                m
                for m in (
                    HVACMode.AUTO,
                    HVACMode.COOL,
                    HVACMode.HEAT,
                    HVACMode.DRY,
                    HVACMode.FAN_ONLY,
                )
                if m in modes
            ],
        ]
        if len(self._attr_hvac_modes) == 1:
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]

        fans = sorted({_fan_to_name(v.get("fan")) for v in self._signals})
        self._attr_fan_modes = [
            f for f in ("auto", "min", "low", "medium", "high", "max") if f in fans
        ] or ["medium"]

        default_mode = next(
            (m for m in self._attr_hvac_modes if m != HVACMode.OFF), HVACMode.COOL
        )
        default_temp = int((self._attr_min_temp + self._attr_max_temp) / 2)
        default_fan = self._attr_fan_modes[0]
        self._state: dict[str, Any] = {
            "power": 0,
            "hvac_mode": default_mode,
            "temp": default_temp,
            "fan": default_fan,
        }

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device registry metadata for this learned-AC entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_unique_name)},
            name=self._device_name,
            manufacturer="STIPS",
            model="IRU1",
            connections={(dr.CONNECTION_NETWORK_MAC, self._device_mac)}
            if self._device_mac
            else set(),
            configuration_url=f"http://{self._device_unique_name}/device_info",
        )

    @property
    def available(self) -> bool:
        """Return latest known availability state for this remote."""
        return bool(self._attr_available)

    @property
    def hvac_mode(self) -> HVACMode:
        """Current HVAC mode derived from the learned AC state."""
        if int(self._state.get("power", 0)) == 0:
            return HVACMode.OFF
        return self._state.get("hvac_mode", HVACMode.COOL)

    @property
    def target_temperature(self) -> float:
        """Current target temperature in Celsius."""
        return float(int(self._state.get("temp", self._attr_min_temp)))

    @property
    def fan_mode(self) -> str:
        """Current fan mode label."""
        return _fan_to_name(self._state.get("fan", "medium"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose non-sensitive metadata for the learned-AC remote."""
        return {
            "device_online": self._device_online,
            "remote_type": self._remote_type,
            "learned_signal_count": len(self._signals),
        }

    async def async_turn_on(self) -> None:
        """Turn the remote on using the best matching learned signal."""
        if self.hvac_mode == HVACMode.OFF:
            mode = next(
                (m for m in self._attr_hvac_modes if m != HVACMode.OFF), HVACMode.COOL
            )
            await self._send_state(power=1, hvac_mode=mode)
            return
        await self._send_state(power=1)

    async def async_turn_off(self) -> None:
        """Turn the remote off using the learned power-off signal when available."""
        if self._power_off_signal:
            await self._post_signal(self._power_off_signal)
            self._state["power"] = 0
            self.async_write_ha_state()
            return
        raise HomeAssistantError(
            "This learned AC remote does not have a dedicated power-off signal"
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Apply a new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        await self._send_state(power=1, hvac_mode=hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Apply a new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            raise HomeAssistantError("Temperature is required")
        requested = int(float(kwargs[ATTR_TEMPERATURE]))
        requested = max(int(self.min_temp), min(int(self.max_temp), requested))
        await self._send_state(power=1, temp=requested)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Apply a new fan mode."""
        # Validate that the requested fan mode is supported before normalizing
        if fan_mode.strip().lower() not in self._attr_fan_modes:
            raise HomeAssistantError(f"Unsupported fan mode: {fan_mode}")
        key = _fan_to_name(fan_mode)
        await self._send_state(power=1, fan=key)

    async def _send_state(self, **overrides: Any) -> None:
        payload_state = dict(self._state)
        payload_state.update(overrides)
        if int(payload_state.get("power", 0)) == 0 and self._power_off_signal:
            await self._post_signal(self._power_off_signal)
            self._state = payload_state
            self.async_write_ha_state()
            return

        hvac_mode = payload_state.get("hvac_mode", HVACMode.COOL)
        temp = int(payload_state.get("temp", self._attr_min_temp))
        fan = _fan_to_name(payload_state.get("fan", "medium"))
        signal = _pick_best_learned_signal(self._signals, hvac_mode, temp, fan)
        if (
            not signal
            and self._power_on_signal
            and int(payload_state.get("power", 1)) == 1
        ):
            await self._post_signal(self._power_on_signal)
            self._state = payload_state
            self.async_write_ha_state()
            return
        if not signal:
            raise HomeAssistantError(
                "No learned AC signal matches requested mode/temp/fan for this remote"
            )

        await self._post_signal(signal)
        self._state = payload_state
        self.async_write_ha_state()

    async def _post_signal(self, signal: str) -> None:
        hosts, live_ip = await async_build_control_hosts(
            self.hass,
            device_unique_name=self._device_unique_name,
            backend_ip=self._device_ip,
        )
        if not hosts:
            raise HomeAssistantError(
                "Device host is missing; verify the IRU is online and its mDNS name resolves, "
                "then reload or reconfigure the integration."
            )
        if live_ip:
            self._device_ip_live = live_ip

        session = async_get_clientsession(self.hass)
        auth = _local_http_auth()
        timeout = aiohttp.ClientTimeout(
            total=3, connect=1.5, sock_connect=1.5, sock_read=2
        )
        params = {
            "signal": signal,
            "frequency": str(self._frequency),
            "remoteType": self._remote_type,
        }
        last_error: Exception | None = None
        for host in hosts:
            url = str(URL.build(scheme="http", host=host, path="/local-ir/send"))
            try:
                async with session.post(
                    url, data=params, auth=auth, timeout=timeout
                ) as response:
                    if response.status >= 400:
                        body = await response.text()
                        last_error = HomeAssistantError(
                            f"Local IR request failed ({response.status}) via {host}: {body[:160]}"
                        )
                        continue
                    self._attr_available = True
                    return
            except (TimeoutError, aiohttp.ClientError) as err:
                last_error = err
                continue
        if isinstance(last_error, HomeAssistantError):
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"{last_error} | hosts={', '.join(hosts)}")
        if last_error is not None:
            self._attr_available = False
            self.async_write_ha_state()
            detail = str(last_error).strip() or type(last_error).__name__
            raise HomeAssistantError(
                f"Cannot reach IR device locally (hosts: {', '.join(hosts)}): {detail}"
            ) from last_error
        self._attr_available = False
        self.async_write_ha_state()
        raise HomeAssistantError(
            f"Cannot reach IR device locally (hosts: {', '.join(hosts)})"
        )
