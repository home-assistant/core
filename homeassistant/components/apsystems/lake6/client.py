"""Lake_6 local API: parsed data objects and the HTTP transport.

The data classes (Lake6Device / Lake6Energies / Lake6Alarms / Lake6Modes) are
the client layer output and sit between the client and the coordinator:
- Field names match the attribute column of the mapping tables in lake6/const.py
  exactly and double as the entity keys, so the entity layer can read them with
  `lambda d: d.xxx`.
- String to float/int/bool conversion happens here. A field that fails to parse
  becomes None without affecting the other fields of the same response.
- Every class is frozen and kw_only: a snapshot must not change, and fields of
  the same type (14 bools, for instance) have to be named to stay aligned.

Lake6ApiClient handles the HTTP transport and the business code check, while
parse_* turns the `data` object into the classes above. Both layers depend on
const.py only and know nothing about HA entities.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
import logging
import math
from typing import Any, Final, Literal

import aiohttp

from .const import (
    LAKE6_BATTERY_STATUS_TO_STATE,
    LAKE6_CODE_DESCRIPTIONS,
    LAKE6_CODE_SUCCESS,
    LAKE6_CONTROL_PANEL_MODE_ACTIVE,
    LAKE6_CONTROL_PANEL_TIME_FORMATS,
    LAKE6_DEFAULT_PORT,
    LAKE6_ENDPOINT_ALARMS,
    LAKE6_ENDPOINT_CONTROL_PANELS,
    LAKE6_ENDPOINT_DEVICES,
    LAKE6_ENDPOINT_ENERGIES,
    LAKE6_ENDPOINT_MODES,
    LAKE6_MESSAGE_SUCCESS,
    LAKE6_OPERATING_MODE_TO_STATE,
    LAKE6_REQUEST_TIMEOUT,
    LAKE6_TOU_FUNCTION_TO_STATE,
)

_LOGGER = logging.getLogger(__name__)

# The raw nested time_cfg array from /modes, kept for write-back and debugging.
# The decoded view is Lake6TouRule.
type Lake6TimeCfg = list[dict[str, Any]]

# Width of one timestamp for each format: 12 for minutes, 14 for seconds.
_TIMESTAMP_WIDTHS: Final[tuple[tuple[str, int], ...]] = tuple(
    (fmt, len(datetime(2000, 1, 1, 0, 0, 0).strftime(fmt)))
    for fmt in LAKE6_CONTROL_PANEL_TIME_FORMATS
)


@dataclass(frozen=True, kw_only=True)
class Lake6TouRule:
    """A decoded `time_cfg` entry, i.e. one row in the product UI.

    The product keeps exactly one `TM` entry per row, so the slot is flattened
    onto the rule. Any extra `TM` entries the firmware might start sending are
    still preserved verbatim in `Lake6Modes.time_cfg`, which is what write-back
    starts from.
    """

    enabled: bool
    weekdays: list[int]
    # The first and last four digits of the raw T value, decoded to HH:MM.
    start: str | None
    end: str | None
    function: str | None
    power: int | None


type Lake6TouRules = list[Lake6TouRule]


@dataclass(frozen=True, kw_only=True)
class Lake6Device:
    """Parsed `GET /devices` response, fetched once during first refresh.

    Only the fields consumed by HA are kept. `bat_manuf` / `bat_model` are
    returned by the device but absent from the OpenAPI contract, so they are
    intentionally not consumed.
    """

    dev_id: str
    # Raw field `type`, renamed so it does not shadow the builtin.
    device_type: str
    # Raw field dev_ver, where an empty string means the firmware sent none.
    sw_version: str | None
    # Raw field bat_cap in kWh.
    battery_capacity: float | None
    # Raw field rssi in dBm. The device sends a JSON number, not a string.
    rssi: int | None


@dataclass(frozen=True, kw_only=True)
class Lake6Energies:
    """Parsed `GET /energies` response.

    Field names equal the entity keys in `LAKE6_ENERGY_FIELD_TO_ATTR`.
    """

    # bat_soc in percent.
    battery_soc: float | None
    # bat_temp in degrees Celsius.
    battery_temperature: float | None
    # dev_temp in degrees Celsius. The same raw name in /alarms is a protection
    # alarm bit instead, see Lake6Alarms.
    device_temperature: float | None

    # bat_impE: accumulated battery charge energy in kWh.
    battery_charge_energy: float | None
    # bat_expE: accumulated battery discharge energy in kWh.
    battery_discharge_energy: float | None
    # ongrid_expE: accumulated on-grid side output energy in kWh.
    grid_export_energy: float | None
    # ongrid_impE: accumulated on-grid side input energy in kWh.
    grid_import_energy: float | None
    # offgrid_expE: accumulated off-grid side output energy in kWh.
    offgrid_export_energy: float | None
    # offgrid_impE: accumulated off-grid side input energy in kWh.
    offgrid_import_energy: float | None

    # bat_power in W. The device formats power as a plain integer ("486"), so
    # the field is typed as int while the energies are floats.
    battery_power: int | None
    # ongrid_power in W.
    grid_power: int | None
    # offgrid_power in W.
    offgrid_power: int | None

    # bat_status, already mapped through LAKE6_BATTERY_STATUS_TO_STATE.
    battery_status: str | None


@dataclass(frozen=True, kw_only=True)
class Lake6Alarms:
    """Parsed `GET /alarms` response.

    Field names equal the entity keys in `LAKE6_ALARM_FIELD_TO_ATTR`.
    Each raw value is "0" (normal) or "1" (fault), converted to bool.

    device_temperature_protection also comes from the raw field dev_temp, but it
    is not the same thing as Lake6Energies.device_temperature, which carries the
    temperature reading.
    """

    battery_over_temperature: bool | None  # bat_overtemp
    battery_under_temperature: bool | None  # bat_undertemp
    battery_communication_error: bool | None  # bat_comm_err
    battery_over_voltage: bool | None  # bat_overvolt
    battery_under_voltage: bool | None  # bat_undervolt
    battery_over_current: bool | None  # bat_overcur
    battery_internal_error: bool | None  # bat_ie
    device_temperature_protection: bool | None  # dev_temp as an alarm bit
    device_system_error: bool | None  # dev_sys_err
    battery_shutdown: bool | None  # bat_shutdown
    grid_anomaly: bool | None  # grid_anomaly
    offgrid_over_current: bool | None  # offgrid_overcur
    offgrid_short_circuit: bool | None  # offgrid_shortcir
    battery_calibration: bool | None  # bat_cal


@dataclass(frozen=True, kw_only=True)
class Lake6Modes:
    """Parsed `GET /modes` response.

    Field names equal the entity keys in `LAKE6_MODE_FIELD_TO_ATTR`.
    The entity min/max owns the ranges; this layer only converts types and lets
    the returned code decide whether a write succeeded.
    """

    # mode, already mapped through LAKE6_OPERATING_MODE_TO_STATE.
    operating_mode: str | None
    # eco as a bool.
    eco: bool | None

    # dod in percent. The product calls it backupSoc, the lowest state of charge
    # backup mode may discharge to, so a larger value is more conservative.
    depth_of_discharge: int | None

    # The raw values, kept for write-back and debugging.
    time_cfg: Lake6TimeCfg

    # The decoded view used by the sensors, derived from time_cfg.
    tou_rules: Lake6TouRules


@dataclass(frozen=True, kw_only=True)
class Lake6ControlPanelWindow:
    """One decoded `MI1` pair: a wall-clock slot with its signed power.

    `power` keeps the raw sign: positive discharges, negative charges and zero
    means standby. The device reports local wall-clock time, so the two
    timestamps are naive datetimes on purpose.
    """

    start: datetime
    end: datetime
    power: int


type Lake6ControlPanelWindows = list[Lake6ControlPanelWindow]


@dataclass(frozen=True, kw_only=True)
class Lake6ControlPanel:
    """Parsed `GET /control-panels` response.

    `mode` is the run state, not a setting: `"1"` only exists while a one-time
    run is in progress, after which the device clears `MI1` and restores the
    long-term mode.
    """

    active: bool
    windows: Lake6ControlPanelWindows
    # Width of one side of the echoed `MI1.time` (12 for the 24 digit form, 14
    # for 28). A write must use this width or the device ignores it silently.
    # None while idle, because MI1 is empty.
    timestamp_width: int | None = None


def _to_float(value: object) -> float | None:
    """Convert a raw JSON value to float, or None when not convertible.

    The parameter is typed as object on purpose: the device does not stick to
    the documented string format, since rssi arrives as a JSON number. Accepting
    only str would raise AttributeError and break the whole setup call.

    NaN and infinity are rejected because HA rejects non-finite sensor values.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return result if math.isfinite(result) else None


def _to_int(value: object) -> int | None:
    """Convert a raw JSON value to int, or None when not convertible.

    String input goes through float first so that "20.0" is accepted.
    Fractional values are truncated, matching how the device rounds dod.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        return int(parsed) if math.isfinite(parsed) else None
    return None


def _to_bool(value: object) -> bool | None:
    """Convert 0/1 (int or str) to bool, or None for anything else.

    The raw alarm fields are documented as "0"/"1" strings, but ints are
    accepted too since the device is not consistent about quoting.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 0:
            return False
        if value == 1:
            return True
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if normalized == "0":
            return False
        if normalized == "1":
            return True
    return None


def _to_enum_state(value: object, mapping: Mapping[str, str]) -> str | None:
    """Map a raw numeric code to its semantic state string.

    Unknown codes yield None rather than raising: a firmware adding a new
    mode must not break the entities that still work.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        key = str(value)
    elif isinstance(value, str):
        key = value.strip()
    else:
        return None
    return mapping.get(key)


def _parse_sw_version(value: object) -> str | None:
    """Normalize the firmware version, mapping empty values to None."""
    if not isinstance(value, str):
        return None
    version = value.strip()
    return version or None


def _to_time_cfg(value: object) -> Lake6TimeCfg:
    """Return the raw time_cfg entries, dropping anything that is not an object."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _to_hhmm(fragment: str) -> str | None:
    """Decode a 4-digit `HHMM` fragment into `HH:MM`."""
    if len(fragment) != 4 or not fragment.isdigit():
        return None
    hours, minutes = int(fragment[:2]), int(fragment[2:])
    if hours > 23 or minutes > 59:
        return None
    return f"{hours:02d}:{minutes:02d}"


def _parse_tou_rule(item: object) -> Lake6TouRule | None:
    """Decode one `time_cfg` entry.

    `E` defaults to enabled when absent, and the firmware keeps `TM` populated
    for disabled rules, so disabled rows are parsed as usual.
    """
    if not isinstance(item, dict):
        return None
    raw_weekdays = item.get("W")
    weekdays = (
        sorted({day for day in raw_weekdays if isinstance(day, int) and 1 <= day <= 7})
        if isinstance(raw_weekdays, list)
        else []
    )
    raw_slots = item.get("TM")
    slot = raw_slots[0] if isinstance(raw_slots, list) and raw_slots else None
    start = end = None
    function = None
    power = None
    if isinstance(slot, dict):
        raw_time = slot.get("T")
        if isinstance(raw_time, str) and len(raw_time) == 8 and raw_time.isdigit():
            start = _to_hhmm(raw_time[:4])
            end = _to_hhmm(raw_time[4:])
        function = LAKE6_TOU_FUNCTION_TO_STATE.get(str(slot.get("F")))
        params = slot.get("FI")
        power = _to_int(params.get("P")) if isinstance(params, Mapping) else None
    return Lake6TouRule(
        enabled=str(item.get("E", "1")) != "0",
        weekdays=weekdays,
        start=start,
        end=end,
        function=function,
        power=power,
    )


def _to_tou_rules(value: object) -> Lake6TouRules:
    """Return the decoded schedule, dropping entries that are not objects."""
    if not isinstance(value, list):
        return []
    return [rule for rule in map(_parse_tou_rule, value) if rule is not None]


def parse_device(raw: Mapping[str, Any]) -> Lake6Device:
    """Parse a `GET /devices` payload.

    Raises:
        ValueError: When `dev_id` is missing or blank. It feeds the unique id
            and the registry serial number, so a device without it cannot be
            represented.
    """
    dev_id = raw.get("dev_id")
    if not isinstance(dev_id, str) or not dev_id.strip():
        raise ValueError("GET /devices response has no usable dev_id")

    device_type = raw.get("type")
    return Lake6Device(
        dev_id=dev_id.strip(),
        device_type=device_type.strip() if isinstance(device_type, str) else "",
        sw_version=_parse_sw_version(raw.get("dev_ver")),
        battery_capacity=_to_float(raw.get("bat_cap")),
        rssi=_to_int(raw.get("rssi")),
    )


def parse_energies(raw: Mapping[str, Any]) -> Lake6Energies:
    """Parse a `GET /energies` payload.

    The three power fields go through `_to_int` because the device formats them
    as plain integers ("486"), unlike the one-decimal SOC ("30.0") and the
    four-to-five decimal energies ("57.28800").
    """
    return Lake6Energies(
        battery_soc=_to_float(raw.get("bat_soc")),
        battery_temperature=_to_float(raw.get("bat_temp")),
        device_temperature=_to_float(raw.get("dev_temp")),
        battery_charge_energy=_to_float(raw.get("bat_impE")),
        battery_discharge_energy=_to_float(raw.get("bat_expE")),
        grid_export_energy=_to_float(raw.get("ongrid_expE")),
        grid_import_energy=_to_float(raw.get("ongrid_impE")),
        offgrid_export_energy=_to_float(raw.get("offgrid_expE")),
        offgrid_import_energy=_to_float(raw.get("offgrid_impE")),
        battery_power=_to_int(raw.get("bat_power")),
        grid_power=_to_int(raw.get("ongrid_power")),
        offgrid_power=_to_int(raw.get("offgrid_power")),
        battery_status=_to_enum_state(
            raw.get("bat_status"), LAKE6_BATTERY_STATUS_TO_STATE
        ),
    )


def parse_alarms(raw: Mapping[str, Any]) -> Lake6Alarms:
    """Parse a `GET /alarms` payload.

    Every field is a "0"/"1" string; "1" means the fault is active.
    """
    return Lake6Alarms(
        battery_over_temperature=_to_bool(raw.get("bat_overtemp")),
        battery_under_temperature=_to_bool(raw.get("bat_undertemp")),
        battery_communication_error=_to_bool(raw.get("bat_comm_err")),
        battery_over_voltage=_to_bool(raw.get("bat_overvolt")),
        battery_under_voltage=_to_bool(raw.get("bat_undervolt")),
        battery_over_current=_to_bool(raw.get("bat_overcur")),
        battery_internal_error=_to_bool(raw.get("bat_ie")),
        device_temperature_protection=_to_bool(raw.get("dev_temp")),
        device_system_error=_to_bool(raw.get("dev_sys_err")),
        battery_shutdown=_to_bool(raw.get("bat_shutdown")),
        grid_anomaly=_to_bool(raw.get("grid_anomaly")),
        offgrid_over_current=_to_bool(raw.get("offgrid_overcur")),
        offgrid_short_circuit=_to_bool(raw.get("offgrid_shortcir")),
        battery_calibration=_to_bool(raw.get("bat_cal")),
    )


def parse_modes(raw: Mapping[str, Any]) -> Lake6Modes:
    """Parse a `GET /modes` payload.

    `power_limit` was dropped in V1.5.1 and `backup_charP` in V1.5.2. Older
    firmware still returns them, but they are ignored on purpose: no field, no
    entity, no round-trip.
    """
    return Lake6Modes(
        operating_mode=_to_enum_state(raw.get("mode"), LAKE6_OPERATING_MODE_TO_STATE),
        eco=_to_bool(raw.get("eco")),
        depth_of_discharge=_to_int(raw.get("dod")),
        time_cfg=_to_time_cfg(raw.get("time_cfg")),
        tou_rules=_to_tou_rules(raw.get("time_cfg")),
    )


def _parse_control_panel_span(
    value: object,
) -> tuple[datetime, datetime, int] | None:
    """Decode one `YYYYMMDDHHMM(SS)`x2 `MI1.time` entry.

    V1.5.2 documents the 28 character form (with seconds), while firmware built
    against V1.4 or older expects 24 (up to the minute), so both widths are
    accepted. Anything else is dropped rather than raising: one malformed row
    must not hide the others.

    Returns:
        The window plus the width of one timestamp, so the caller can mirror
        the device's own format on the next write.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt, width in _TIMESTAMP_WIDTHS:
        if len(text) != width * 2:
            continue
        try:
            return (
                datetime.strptime(text[:width], fmt),
                datetime.strptime(text[width:], fmt),
                width,
            )
        except ValueError:
            continue
    return None


def parse_control_panel(raw: Mapping[str, Any]) -> Lake6ControlPanel:
    """Parse a `GET /control-panels` payload.

    `MI1.time` and `MI1.power` are parallel arrays paired by index, so an entry
    is only kept when both halves are usable; a power without its slot (or the
    reverse) would silently shift every following pair onto the wrong window.

    `time` is still read when `mode` is "0": the device keeps the previous
    `MI1` after a stop, and its width is the only hint for which timestamp
    layout a request has to use. Those leftovers are not reported as windows,
    since nothing will execute them.
    """
    active = str(raw.get("mode", "")).strip() == LAKE6_CONTROL_PANEL_MODE_ACTIVE
    windows: list[Lake6ControlPanelWindow] = []
    widths: set[int] = set()
    params = raw.get("MI1")
    if isinstance(params, Mapping):
        raw_times = params.get("time")
        raw_powers = params.get("power")
        if isinstance(raw_times, list) and isinstance(raw_powers, list):
            for raw_time, raw_power in zip(raw_times, raw_powers, strict=False):
                span = _parse_control_panel_span(raw_time)
                power = _to_int(raw_power)
                if span is None or power is None:
                    continue
                widths.add(span[2])
                if active:
                    windows.append(
                        Lake6ControlPanelWindow(start=span[0], end=span[1], power=power)
                    )
    return Lake6ControlPanel(
        active=active,
        windows=windows,
        # A single device never mixes both widths; a mix means the echo is
        # broken, and guessing would be worse than reporting None.
        timestamp_width=next(iter(widths)) if len(widths) == 1 else None,
    )


class Lake6ApiError(Exception):
    """Raised when a Lake_6 request fails or the device reports an error code.

    `code` is the business code taken from the response body, or None when the
    failure happened below the API layer (network, HTTP status, malformed JSON).
    """

    def __init__(self, message: str, code: int | None = None) -> None:
        """Initialize the error."""
        self.code = code
        self.message = message
        super().__init__(f"code {code}: {message}" if code is not None else message)


class Lake6ApiClient:
    """HTTP client for the Lake_6 local API.

    Every endpoint answers with `{"data": {...}, "code": 200, ...}`, so success
    is decided by the business code rather than by the HTTP status alone.
    """

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession,
        port: int = LAKE6_DEFAULT_PORT,
        timeout: int = LAKE6_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize the client."""
        self._base_url = f"http://{host}:{port}"
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def async_get(
        self, endpoint: str, *, code_optional: bool = False
    ) -> dict[str, Any]:
        """Fetch one endpoint and return its `data` object."""
        body = await self._async_request("GET", endpoint, code_optional=code_optional)
        data = body.get("data")
        if not isinstance(data, dict):
            raise Lake6ApiError(f"GET {endpoint} returned no data object")
        return data

    async def async_get_device(self) -> Lake6Device:
        """Return the static device identity."""
        data = await self.async_get(LAKE6_ENDPOINT_DEVICES)
        try:
            return parse_device(data)
        except ValueError as err:
            raise Lake6ApiError(str(err)) from err

    async def async_get_energies(self) -> Lake6Energies:
        """Return the live energy and power snapshot."""
        data = await self.async_get(LAKE6_ENDPOINT_ENERGIES)
        return parse_energies(data)

    async def async_get_alarms(self) -> Lake6Alarms:
        """Return the alarm bitfield snapshot."""
        data = await self.async_get(LAKE6_ENDPOINT_ALARMS)
        return parse_alarms(data)

    async def async_get_modes(self) -> Lake6Modes:
        """Return the current mode configuration."""
        data = await self.async_get(LAKE6_ENDPOINT_MODES)
        return parse_modes(data)

    async def async_get_control_panel(self) -> Lake6ControlPanel:
        """Return the one-time manual control state.

        This endpoint's envelope may omit `code`, so the business check falls
        back to `message` here only.
        """
        data = await self.async_get(LAKE6_ENDPOINT_CONTROL_PANELS, code_optional=True)
        return parse_control_panel(data)

    async def async_set_modes(self, **changes: Any) -> None:
        """Write the changed mode fields only.

        Every scalar field is a string; `time_cfg` is the single exception and
        carries the complete rule list, because the device replaces the whole
        array rather than merging it.
        """
        await self.async_post(LAKE6_ENDPOINT_MODES, changes)

    async def async_set_control_panel(self, payload: dict[str, Any]) -> None:
        """Send a one-time manual control request.

        The payload always carries the complete `MI1` object: the device
        replaces the configuration rather than merging it, and `mode="1"`
        requires `MI1` while `mode="0"` takes an empty object.
        """
        await self.async_post(
            LAKE6_ENDPOINT_CONTROL_PANELS, payload, code_optional=True
        )

    async def async_post(
        self, endpoint: str, payload: dict[str, Any], *, code_optional: bool = False
    ) -> None:
        """Post a payload and return once the device accepts it.

        Callers send only the fields they change: the device keeps the current
        value of every omitted field.
        """
        await self._async_request(
            "POST", endpoint, payload, code_optional=code_optional
        )

    async def _async_request(
        self,
        method: Literal["GET", "POST"],
        endpoint: str,
        payload: dict[str, Any] | None = None,
        *,
        code_optional: bool = False,
    ) -> dict[str, Any]:
        """Perform one request and validate the transport and business layers."""
        body: object = None
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{endpoint}",
                json=payload,
                timeout=self._timeout,
            ) as response:
                if response.status != HTTPStatus.OK:
                    raise Lake6ApiError(
                        f"{method} {endpoint} returned HTTP {response.status}"
                    )
                try:
                    body = await response.json(content_type=None)
                except ValueError as err:
                    raise Lake6ApiError(
                        f"{method} {endpoint} returned invalid JSON"
                    ) from err
        except TimeoutError as err:
            raise Lake6ApiError(f"{method} {endpoint} timed out") from err
        except aiohttp.ClientError as err:
            raise Lake6ApiError(f"{method} {endpoint} failed: {err}") from err

        if not isinstance(body, dict):
            raise Lake6ApiError(f"{method} {endpoint} returned a non-object body")

        self._raise_for_code(endpoint, body, code_optional)
        _LOGGER.debug("%s %s succeeded", method, endpoint)
        return body

    @staticmethod
    def _raise_for_code(
        endpoint: str, body: dict[str, Any], code_optional: bool
    ) -> None:
        """Convert a non-success business code into Lake6ApiError.

        `/control-panels` is the one endpoint whose envelope may omit `code`
        (the real GET response only carries `message`). There the message is
        the only signal left; every other endpoint keeps failing on a missing
        code so a broken body is never mistaken for success.
        """
        code = body.get("code")
        if code is None and code_optional:
            message = body.get("message")
            if message == LAKE6_MESSAGE_SUCCESS:
                return
            raise Lake6ApiError(f"{endpoint} reported {message!r}")
        if not isinstance(code, int):
            raise Lake6ApiError(f"{endpoint} response has no numeric code")
        if code == LAKE6_CODE_SUCCESS:
            return
        description = LAKE6_CODE_DESCRIPTIONS.get(code, "unknown code")
        raise Lake6ApiError(f"{endpoint}: {description}", code)
