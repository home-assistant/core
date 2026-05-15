from __future__ import annotations

from dataclasses import dataclass
import asyncio
from typing import Any

from aiohttp import ClientError

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_TIMEOUT_S


class RfmGatewayError(Exception):
    """Base error for RFM Gateway communication failures."""


class RfmGatewayConnectionError(RfmGatewayError):
    """Raised when the gateway is unreachable."""


class RfmGatewayProtocolError(RfmGatewayError):
    """Raised when the gateway response is malformed or indicates failure."""


@dataclass(slots=True)
class RfmCapabilities:
    supported_frequency_ranges: list[tuple[int, int]]
    supported_modulations: list[str]
    device_name: str | None = None


class RfmGatewayClient:
    def __init__(
        self,
        hass,
        base_url: str,
    ) -> None:
        self._hass = hass
        self._base_url = base_url.rstrip("/")

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    async def async_get_capabilities(self) -> RfmCapabilities:
        session = async_get_clientsession(self._hass)
        url = f"{self._base_url}/api/rf/capabilities"

        try:
            async with session.get(
                url,
                headers=self._headers(),
                timeout=DEFAULT_TIMEOUT_S,
            ) as resp:
                if resp.status != 200:
                    txt = await resp.text()
                    raise RfmGatewayProtocolError(
                        f"Capability request failed with HTTP {resp.status}: {txt}"
                    )

                payload = await resp.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise RfmGatewayConnectionError(f"Timeout while requesting {url}") from err
        except ClientError as err:
            raise RfmGatewayConnectionError(str(err)) from err

        if not isinstance(payload, dict):
            raise RfmGatewayProtocolError("Capabilities payload must be a JSON object")

        ranges = self._parse_ranges(payload.get("supported_frequency_ranges", []))
        if not ranges:
            raise RfmGatewayProtocolError("No supported_frequency_ranges provided")

        modulations_raw = payload.get("supported_modulations", ["ook"])
        if not isinstance(modulations_raw, list):
            raise RfmGatewayProtocolError("supported_modulations must be a list")

        modulations = [str(x).strip().lower() for x in modulations_raw if str(x).strip()]
        if not modulations:
            modulations = ["ook"]

        device_name = payload.get("device_name")
        if device_name is not None:
            device_name = str(device_name)

        return RfmCapabilities(
            supported_frequency_ranges=ranges,
            supported_modulations=modulations,
            device_name=device_name,
        )

    async def async_send_raw(
        self,
        *,
        frequency_hz: int,
        modulation: str,
        repeat_count: int,
        timings_us: list[int],
    ) -> None:
        session = async_get_clientsession(self._hass)
        url = f"{self._base_url}/api/rf/transmit"
        payload: dict[str, Any] = {
            "frequency_hz": frequency_hz,
            "modulation": modulation,
            "repeat_count": repeat_count,
            "timings_us": timings_us,
        }

        try:
            async with session.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=DEFAULT_TIMEOUT_S,
            ) as resp:
                if resp.status != 200:
                    txt = await resp.text()
                    raise RfmGatewayProtocolError(
                        f"Transmit failed with HTTP {resp.status}: {txt}"
                    )

                try:
                    body = await resp.json(content_type=None)
                except ValueError:
                    return

                if isinstance(body, dict):
                    ok = bool(body.get("ok", True))
                    if not ok:
                        msg = str(body.get("error", "gateway returned ok=false"))
                        raise RfmGatewayProtocolError(msg)
        except asyncio.TimeoutError as err:
            raise RfmGatewayConnectionError(f"Timeout while requesting {url}") from err
        except ClientError as err:
            raise RfmGatewayConnectionError(str(err)) from err

    @staticmethod
    def _parse_ranges(raw: Any) -> list[tuple[int, int]]:
        if not isinstance(raw, list):
            return []

        parsed: list[tuple[int, int]] = []
        for item in raw:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            try:
                low = int(item[0])
                high = int(item[1])
            except (TypeError, ValueError):
                continue

            if low <= 0 or high <= 0 or low > high:
                continue
            parsed.append((low, high))

        return parsed