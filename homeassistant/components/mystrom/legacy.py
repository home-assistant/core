"""Legacy support for myStrom v1 switches without type field.

This module provides a minimal drop-in replacement for pymystrom.switch.MyStromSwitch
for devices that do not expose a "type" key in their info/report responses
(e.g., CH v1 on firmware 2.x), to restore compatibility with HA 2025.8+.

TEMPORARY: Remove once python-mystrom provides a release that tolerates missing
"type" in device info (see PR home-assistant-ecosystem/python-mystrom#60).
"""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError

from pymystrom.exceptions import MyStromConnectionError

REPORT_ENDPOINTS: tuple[str, ...] = ("/report", "/api/v1/report")


class LegacyMyStromV1Switch:
    """Minimal async HTTP client for legacy myStrom v1 switches.

    Exposes a subset of the pymystrom.MyStromSwitch interface used by HA:
    - get_state()
    - turn_on()/turn_off()
    - properties: relay, consumption, consumedWs, temperature, firmware, mac, uri
    """

    def __init__(self, ip: str, mac: str | None, firmware: str | None, session) -> None:
        self._ip = ip
        self._mac = mac
        self._firmware = firmware
        self._session = session
        self._relay: bool | None = None
        self._consumption: float | None = None
        self._consumed_ws: float | None = None
        self._temperature: float | None = None

    # --- properties expected by the HA integration ---
    @property
    def mac(self) -> str | None:
        return self._mac

    @property
    def firmware(self) -> str | None:
        return self._firmware

    @property
    def uri(self) -> str:
        return f"http://{self._ip}"

    @property
    def relay(self) -> bool | None:
        return self._relay

    @property
    def consumption(self) -> float | None:
        return self._consumption

    @property
    def consumedWs(self) -> float | None:  # noqa: N802 (match library attribute casing)
        return self._consumed_ws

    @property
    def temperature(self) -> float | None:
        return self._temperature

    # --- operations ---
    async def get_state(self) -> None:
        """Fetch and cache the current state from the device.

        Tries multiple known report endpoints used across firmware generations.
        """
        last_error: Exception | None = None
        for suffix in REPORT_ENDPOINTS:
            url = f"http://{self._ip}{suffix}"
            try:
                async with self._session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        last_error = RuntimeError(f"HTTP {resp.status}")
                        continue
                    data: dict[str, Any] = await resp.json(content_type=None)
                    # Map common keys found on older firmwares
                    self._relay = bool(data.get("relay") or data.get("on"))
                    # Power in W
                    self._consumption = _to_float_or_none(
                        data.get("power") or data.get("Power")
                    )
                    # Average energy consumed per second since last report
                    self._consumed_ws = _to_float_or_none(data.get("Ws"))
                    self._temperature = _to_float_or_none(
                        data.get("temperature") or data.get("Temp")
                    )
                    # Optional metadata refresh if present
                    self._firmware = (
                        str(data.get("version")) if data.get("version") else self._firmware
                    )
                    self._mac = str(data.get("mac")) if data.get("mac") else self._mac
                    return
            except (ClientError, asyncio.TimeoutError) as err:
                last_error = err
                continue
            except Exception as err:  # Be defensive for unexpected formats
                last_error = err
                continue
        # If we reach here, all attempts failed
        raise MyStromConnectionError(str(last_error) if last_error else "Unknown error")

    async def turn_on(self) -> None:
        await self._set_relay_state(True)

    async def turn_off(self) -> None:
        await self._set_relay_state(False)

    async def _set_relay_state(self, state: bool) -> None:
        url = f"http://{self._ip}/relay?state={'1' if state else '0'}"
        try:
            async with self._session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    raise MyStromConnectionError(f"HTTP {resp.status}")
                # Some firmwares return JSON or plain text; ignore body
                self._relay = state
        except (ClientError, asyncio.TimeoutError) as err:
            raise MyStromConnectionError(str(err)) from err


def _to_float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

