"""SolarEdge Developer Platform V2 API client."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from http import HTTPStatus
import time
from typing import Any

from aiohttp import ClientError, ClientSession

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .const import API_BASE_URL

type AccessTokenProvider = Callable[[], Awaitable[str]]


class SolarEdgeApiError(Exception):
    """Base SolarEdge API error."""


class SolarEdgeAuthError(ConfigEntryAuthFailed, SolarEdgeApiError):
    """SolarEdge authentication error."""


class SolarEdgeConnectionError(ClientError, SolarEdgeApiError):
    """SolarEdge connection error."""


class SolarEdgeNotFoundError(SolarEdgeApiError):
    """SolarEdge resource is not available for this site."""


class SolarEdgeRateLimitError(UpdateFailed, SolarEdgeApiError):
    """SolarEdge rate or credit limit error."""

    def __init__(self, *, retry_after: int | None, monthly_limit: bool) -> None:
        """Initialize the error."""
        super().__init__(
            "Monthly API credit limit reached"
            if monthly_limit
            else "API call rate limit reached"
        )
        self.retry_after = retry_after
        self.monthly_limit = monthly_limit


class SolarEdgeV2:
    """Client for the SolarEdge Developer Platform V2 API."""

    def __init__(
        self,
        session: ClientSession,
        access_token_provider: AccessTokenProvider,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._access_token_provider = access_token_provider
        self._cache: dict[str, tuple[float, dict[str, Any] | list[Any]]] = {}
        self._monthly_limit_until: datetime | None = None
        self._meter_supported: bool | None = None

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, str | list[str]] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Make an authenticated API request."""
        if (
            self._monthly_limit_until is not None
            and dt_util.now() < self._monthly_limit_until
        ):
            raise SolarEdgeRateLimitError(retry_after=None, monthly_limit=True)
        access_token = await self._access_token_provider()
        try:
            response = await self._session.get(
                f"{API_BASE_URL}{path}",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
        except ClientError as err:
            raise SolarEdgeConnectionError from err

        if response.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise SolarEdgeAuthError
        if response.status == HTTPStatus.NOT_FOUND:
            raise SolarEdgeNotFoundError
        if response.status == HTTPStatus.TOO_MANY_REQUESTS:
            retry_after_header = response.headers.get("retry-after")
            retry_after = (
                int(retry_after_header)
                if retry_after_header and retry_after_header.isdigit()
                else None
            )
            remaining_minute = response.headers.get("x-ratelimit-remaining-minute")
            monthly_limit = (
                retry_after is None
                and remaining_minute is not None
                and remaining_minute != "0"
            )
            if monthly_limit:
                now = dt_util.now()
                self._monthly_limit_until = (
                    now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    + timedelta(days=32)
                ).replace(day=1)
            raise SolarEdgeRateLimitError(
                retry_after=retry_after, monthly_limit=monthly_limit
            )
        try:
            response.raise_for_status()
            result = await response.json()
        except (ClientError, ValueError) as err:
            raise SolarEdgeConnectionError from err
        if not isinstance(result, dict | list):
            raise SolarEdgeApiError("Unexpected API response")
        return result

    async def _cached_request(
        self,
        cache_key: str,
        max_age: timedelta,
        path: str,
        *,
        params: dict[str, str | list[str]] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Return a cached API response when it is fresh enough."""
        now = time.monotonic()
        if (cached := self._cache.get(cache_key)) and now - cached[
            0
        ] < max_age.total_seconds():
            return cached[1]
        result = await self._request(path, params=params)
        self._cache[cache_key] = (now, result)
        return result

    async def get_details(self, site_id: str) -> dict[str, Any]:
        """Return site details in the V1-compatible shape."""
        response = await self._cached_request(
            f"details:{site_id}",
            timedelta(hours=24),
            f"/sites/{site_id}",
        )
        if not isinstance(response, dict):
            raise SolarEdgeApiError("Unexpected site details response")
        site = _mapping(response.get("site")) or response
        return {
            "details": {
                "id": str(site.get("siteId", site_id)),
                "name": site.get("name"),
                "status": site.get("activationStatus"),
                "peakPower": site.get("peakPower"),
                "installationDate": site.get("installationDate"),
                "lastUpdateTime": site.get("lastUpdateTime"),
                "type": site.get("type"),
                "primaryModule": site.get("primaryModule", {}),
            }
        }

    async def get_overview(self, site_id: str) -> dict[str, Any]:
        """Return site overview in the V1-compatible shape."""
        now = dt_util.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)
        year_start = month_start.replace(month=1)

        daily = await self._get_overview(site_id, day_start, now, "day")
        monthly = await self._get_energy(site_id, month_start, now, "month")
        yearly = await self._get_energy(site_id, year_start, now, "year")
        lifetime = await self._cached_request(
            f"lifetime:{site_id}",
            timedelta(hours=24),
            f"/sites/{site_id}/lifetime-energy",
        )
        meter = await self._get_meter_telemetry(site_id, now)

        if not all(
            isinstance(response, dict)
            for response in (daily, monthly, yearly, lifetime, meter)
        ):
            raise SolarEdgeApiError("Unexpected energy response")
        production = _mapping(daily.get("production"))
        current_power = _latest_meter_value(meter, "productionPower")
        if current_power is None:
            power = await self._get_site_power(site_id, now)
            values = _find_list(power, "values")
            current_power = (
                _find_number(values[-1], "value")
                if values
                else _find_number(power, "value")
            )
        return {
            "overview": {
                "lifeTimeData": {
                    "energy": _energy_wh(
                        _find_number(lifetime, "energy", "lifetimeEnergy"),
                        _find_string(lifetime, "units", "unit"),
                    )
                },
                "lastYearData": {"energy": _energy_total_wh(yearly)},
                "lastMonthData": {"energy": _energy_total_wh(monthly)},
                "lastDayData": {
                    "energy": _energy_wh(
                        _find_number(production, "total"),
                        _find_string(production, "units", "unit"),
                    )
                },
                "currentPower": {"power": current_power},
                "lastUpdateTime": _find_string(daily, "lastUpdateTime", "timestamp"),
            }
        }

    async def _get_overview(
        self,
        site_id: str,
        start: datetime,
        end: datetime,
        period: str,
    ) -> dict[str, Any] | list[Any]:
        """Get a site overview for a time period."""
        return await self._cached_request(
            f"overview:{site_id}:{period}:{start.date().isoformat()}",
            timedelta(minutes=55) if period == "day" else timedelta(hours=24),
            f"/sites/{site_id}/overview",
            params={"from": start.isoformat(), "to": end.isoformat()},
        )

    async def _get_energy(
        self,
        site_id: str,
        start: datetime,
        end: datetime,
        period: str,
    ) -> dict[str, Any] | list[Any]:
        """Get total production energy for a time period."""
        return await self._cached_request(
            f"energy:{site_id}:{period}:{start.date().isoformat()}",
            timedelta(hours=24),
            f"/sites/{site_id}/energy",
            params={
                "from": start.isoformat(),
                "to": end.isoformat(),
                "resolution": "TOTAL",
            },
        )

    async def get_inventory(self, site_id: str) -> dict[str, Any]:
        """Return device inventory in the V1-compatible shape."""
        response = await self._cached_request(
            f"devices:{site_id}",
            timedelta(hours=24),
            f"/sites/{site_id}/devices",
            params={
                "types": [
                    "INVERTER",
                    "BATTERY",
                    "METER",
                    "GATEWAY",
                ]
            },
        )
        inventory: dict[str, list[dict[str, Any]]] = {
            "inverters": [],
            "batteries": [],
            "meters": [],
            "gateways": [],
            "sensors": [],
        }
        devices = _device_list(response)
        for device in devices:
            device_type = str(device.get("type", "")).lower()
            key = {
                "inverter": "inverters",
                "battery": "batteries",
                "meter": "meters",
                "gateway": "gateways",
                "sensor": "sensors",
            }.get(device_type)
            if key is None:
                continue
            serial = device.get("serialNumber")
            inventory[key].append({**device, "SN": serial})
        return {"Inventory": inventory}

    async def _get_meter_telemetry(self, site_id: str, now: datetime) -> dict[str, Any]:
        """Get the latest meter telemetry."""
        if self._meter_supported is False:
            return {}
        try:
            result = await self._cached_request(
                f"meter:{site_id}",
                timedelta(minutes=55),
                f"/sites/{site_id}/meters/telemetry",
                params={
                    "from": (now - timedelta(hours=1)).isoformat(),
                    "to": now.isoformat(),
                    "resolution": "QUARTER_HOUR",
                },
            )
        except SolarEdgeNotFoundError:
            self._meter_supported = False
            return {}
        if not isinstance(result, dict):
            raise SolarEdgeApiError("Unexpected meter telemetry response")
        meters = result.get("meters")
        self._meter_supported = (
            bool(meters)
            if isinstance(meters, dict)
            else bool(_find_list(result, "meters", "meter"))
        )
        return result

    async def _get_site_power(self, site_id: str, now: datetime) -> dict[str, Any]:
        """Get latest site production power when no meter is installed."""
        result = await self._cached_request(
            f"power:{site_id}",
            timedelta(minutes=55),
            f"/sites/{site_id}/power",
            params={
                "from": (now - timedelta(hours=1)).isoformat(),
                "to": now.isoformat(),
                "resolution": "QUARTER_HOUR",
                "unit": "W",
            },
        )
        if not isinstance(result, dict):
            raise SolarEdgeApiError("Unexpected site power response")
        return result

    async def get_current_power_flow(self, site_id: str) -> dict[str, Any]:
        """Return meter telemetry in the V1 power-flow shape."""
        now = dt_util.now()
        meter = await self._get_meter_telemetry(site_id, now)
        storage: dict[str, Any] = {}
        if cached_inventory := self._cache.get(f"devices:{site_id}"):
            if any(
                device.get("type") == "BATTERY"
                for device in _device_list(cached_inventory[1])
            ):
                storage = await self._get_storage_telemetry(
                    site_id,
                    now.replace(hour=0, minute=0, second=0, microsecond=0),
                    now,
                )
        production = _latest_meter_value(meter, "productionPower")
        consumption = _latest_meter_value(meter, "consumptionPower")
        imported = _latest_meter_value(meter, "importPower")
        exported = _latest_meter_value(meter, "exportPower")

        exporting = exported is not None and (imported is None or exported > imported)
        grid = exported if exporting else imported
        connections = []
        if grid is not None:
            connections.append(
                {"from": "GRID", "to": "Load"}
                if not exporting
                else {"from": "PV", "to": "GRID"}
            )
        power_flow: dict[str, Any] = {
            "unit": "W",
            "connections": connections,
            "PV": {"status": "Active", "currentPower": production},
            "LOAD": {"status": "Active", "currentPower": consumption},
            "GRID": {"status": "Active", "currentPower": grid},
        }
        charge_power, discharge_power, state_of_energy = _latest_storage_values(storage)
        if charge_power is not None or discharge_power is not None:
            charging = (charge_power or 0) > (discharge_power or 0)
            discharging = (discharge_power or 0) > (charge_power or 0)
            storage_power = charge_power if charging else discharge_power
            if charging:
                power_flow["connections"].append({"from": "PV", "to": "STORAGE"})
            elif discharging:
                power_flow["connections"].append({"from": "STORAGE", "to": "Load"})
            power_flow["STORAGE"] = {
                "status": (
                    "Charging" if charging else "Discharging" if discharging else "Idle"
                ),
                "currentPower": storage_power,
                "chargeLevel": state_of_energy,
            }
        return {"siteCurrentPowerFlow": power_flow}

    async def get_energy_details(
        self,
        site_id: str,
        start: datetime,
        end: datetime,
        *,
        time_unit: str,
    ) -> dict[str, Any]:
        """Return overview totals in the V1 energy-details shape."""
        overview = await self._get_overview(site_id, start, end, "day")
        if not isinstance(overview, dict):
            raise SolarEdgeApiError("Unexpected overview response")
        production = _mapping(overview.get("production"))
        consumption = _mapping(overview.get("consumption"))
        values = {
            "Production": _energy_wh(
                _find_number(production, "total"),
                _find_string(production, "units", "unit"),
            ),
            "SelfConsumption": _energy_wh(
                _find_number(production, "toSelfConsumption"),
                _find_string(production, "units", "unit"),
            ),
            "FeedIn": _energy_wh(
                _find_number(production, "toGrid"),
                _find_string(production, "units", "unit"),
            ),
            "Purchased": _energy_wh(
                _find_number(consumption, "fromGrid"),
                _find_string(consumption, "units", "unit"),
            ),
            "Consumption": _energy_wh(
                _find_number(consumption, "total"),
                _find_string(consumption, "units", "unit"),
            ),
        }
        return {
            "energyDetails": {
                "unit": "Wh",
                "meters": [
                    {
                        "type": meter_type,
                        "values": [{"date": end.isoformat(), "value": value}],
                    }
                    for meter_type, value in values.items()
                    if value is not None
                ],
            }
        }

    async def get_storage_data(
        self,
        site_id: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Return storage telemetry in the V1-compatible shape."""
        response = await self._get_storage_telemetry(site_id, start, end)
        batteries = []
        for battery in _storage_devices(response):
            serial = battery.get("serialNumber")
            telemetry = _find_list(
                battery, "telemetry", "telemetries", "data", "values"
            )
            batteries.append(
                {
                    "serialNumber": serial,
                    "telemetries": [
                        {
                            "timeStamp": item.get("timestamp"),
                            "power": _storage_power(item),
                            "batteryPercentageState": _find_number(
                                item, "stateOfEnergy", "stateOfCharge"
                            ),
                            "lifeTimeEnergyCharged": _find_number(
                                item, "chargeEnergy", "lifetimeEnergyCharged"
                            )
                            or 0,
                            "lifeTimeEnergyDischarged": _find_number(
                                item, "dischargeEnergy", "lifetimeEnergyDischarged"
                            )
                            or 0,
                        }
                        for item in telemetry
                    ],
                }
            )
        return {"storageData": {"batteries": batteries}}

    async def _get_storage_telemetry(
        self, site_id: str, start: datetime, end: datetime
    ) -> dict[str, Any]:
        """Get storage telemetry with quota-aware caching."""
        try:
            result = await self._cached_request(
                f"storage:{site_id}:{start.date().isoformat()}",
                timedelta(hours=4),
                f"/sites/{site_id}/storage/telemetry",
                params={
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                    "resolution": "QUARTER_HOUR",
                },
            )
        except SolarEdgeNotFoundError:
            return {}
        if not isinstance(result, dict):
            raise SolarEdgeApiError("Unexpected storage telemetry response")
        return result


def _mapping(value: Any) -> dict[str, Any]:
    """Return a mapping or an empty mapping."""
    return value if isinstance(value, dict) else {}


def _device_list(data: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Return devices from either documented V2 response shape."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return _find_list(data, "devices", "device")


def _find_list(data: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    """Find a list of mappings in a response."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for value in data.values():
        if isinstance(value, dict) and (result := _find_list(value, *keys)):
            return result
    return []


def _find_number(data: dict[str, Any], *keys: str) -> float | None:
    """Find a numeric value in a mapping."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, int | float):
            return float(value)
    for value in data.values():
        if (
            isinstance(value, dict)
            and (result := _find_number(value, *keys)) is not None
        ):
            return result
    return None


def _find_string(data: dict[str, Any], *keys: str) -> str | None:
    """Find a string value in a mapping."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str):
            return value
    for value in data.values():
        if (
            isinstance(value, dict)
            and (result := _find_string(value, *keys)) is not None
        ):
            return result
    return None


def _energy_wh(value: float | None, unit: str | None) -> float | None:
    """Convert an API energy value to watt-hours."""
    if value is None:
        return None
    return value * {"WH": 1, "KWH": 1000, "MWH": 1_000_000}.get(
        (unit or "WH").upper(), 1
    )


def _energy_total_wh(data: dict[str, Any]) -> float | None:
    """Extract total production energy and convert it to watt-hours."""
    production = _mapping(data.get("production"))
    source = production or data
    unit = _find_string(source, "units", "unit")
    values = _find_list(source, "values")
    if values:
        source = values[-1]
    return _energy_wh(
        _find_number(source, "total", "energy", "value"),
        unit or _find_string(source, "units", "unit"),
    )


def _latest_meter_value(data: dict[str, Any], key: str) -> float | None:
    """Return the latest meter telemetry value."""
    latest: float | None = None
    if isinstance(meters := data.get("meters"), dict):
        for meter in meters.values():
            if (
                isinstance(meter, dict)
                and (value := _latest_metric_value(meter.get(key))) is not None
            ):
                latest = (latest or 0) + value
        return latest
    for meter in _find_list(data, "meters"):
        telemetry = _find_list(meter, "telemetry", "telemetries", "data", "values")
        if telemetry and (value := _find_number(telemetry[-1], key)) is not None:
            latest = (latest or 0) + value
    if latest is not None:
        return latest
    telemetry = _find_list(data, "telemetry", "telemetries", "data", "values")
    if telemetry:
        return _find_number(telemetry[-1], key)
    return _find_number(data, key)


def _storage_power(data: dict[str, Any]) -> float | None:
    """Return signed battery power."""
    charge = _find_number(data, "chargePower")
    discharge = _find_number(data, "dischargePower")
    if charge is None and discharge is None:
        return _find_number(data, "power")
    return (discharge or 0) - (charge or 0)


def _latest_metric_value(metric: Any) -> float | None:
    """Return the latest value from a V2 telemetry metric."""
    if isinstance(metric, int | float):
        return float(metric)
    if not isinstance(metric, dict):
        return None
    values = _find_list(metric, "values")
    if values:
        return _find_number(values[-1], "value")
    return _find_number(metric, "value")


def _storage_devices(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize documented and legacy-compatible storage telemetry."""
    if not isinstance(storage := data.get("storage"), dict):
        return _find_list(data, "batteries", "storage")

    batteries: list[dict[str, Any]] = []
    for serial, device in storage.items():
        if not isinstance(device, dict):
            continue
        telemetry_by_timestamp: dict[str | None, dict[str, Any]] = {}
        for key in (
            "chargePower",
            "dischargePower",
            "stateOfEnergy",
            "stateOfCharge",
            "chargeEnergy",
            "dischargeEnergy",
            "lifetimeEnergyCharged",
            "lifetimeEnergyDischarged",
        ):
            metric = device.get(key)
            if not isinstance(metric, dict):
                continue
            for point in _find_list(metric, "values"):
                timestamp = _find_string(point, "timestamp")
                telemetry_by_timestamp.setdefault(timestamp, {"timestamp": timestamp})[
                    key
                ] = _find_number(point, "value")
        batteries.append(
            {
                "serialNumber": serial,
                "telemetry": list(telemetry_by_timestamp.values()),
            }
        )
    return batteries


def _latest_storage_values(
    data: dict[str, Any],
) -> tuple[float | None, float | None, float | None]:
    """Return aggregate latest storage telemetry."""
    charge_power: float | None = None
    discharge_power: float | None = None
    state_of_energy: float | None = None
    for battery in _storage_devices(data):
        telemetry = _find_list(battery, "telemetry", "telemetries", "data", "values")
        if not telemetry:
            continue
        latest = telemetry[-1]
        if (value := _find_number(latest, "chargePower")) is not None:
            charge_power = (charge_power or 0) + value
        if (value := _find_number(latest, "dischargePower")) is not None:
            discharge_power = (discharge_power or 0) + value
        if (
            value := _find_number(latest, "stateOfEnergy", "stateOfCharge")
        ) is not None:
            state_of_energy = value
    return charge_power, discharge_power, state_of_energy
