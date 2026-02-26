"""Local Tuya transport for Eufy RoboVac."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class EufyRoboVacLocalApiError(HomeAssistantError):
    """Raised when local API communication fails."""


@dataclass(slots=True)
class EufyRoboVacLocalApi:
    """Minimal local API wrapper around tinytuya Device."""

    host: str
    device_id: str
    local_key: str
    protocol_version: str
    timeout: float = 5.0

    def _create_device(self):
        """Create a configured tinytuya Device instance."""
        import tinytuya

        device = tinytuya.Device(
            dev_id=self.device_id,
            address=self.host,
            local_key=self.local_key,
            persist=False,
        )
        device.set_version(float(self.protocol_version))
        device.set_socketTimeout(self.timeout)
        return device

    def _send_dps_sync(self, dps: dict[str, Any]) -> dict[str, Any]:
        """Send DPS command payload synchronously."""
        device = None
        try:
            device = self._create_device()
            response = device.set_multiple_values(dps)
        except Exception as err:  # noqa: BLE001
            raise EufyRoboVacLocalApiError(
                f"Failed sending DPS to {self.host}: {err}"
            ) from err
        finally:
            if device is not None:
                _close = getattr(device, "close", None)
                if callable(_close):
                    _close()

        if not isinstance(response, dict):
            return {}
        return response

    async def async_send_dps(
        self, hass: HomeAssistant, dps: dict[str, Any]
    ) -> dict[str, Any]:
        """Send DPS command payload asynchronously."""
        return await hass.async_add_executor_job(self._send_dps_sync, dps)

    def _get_dps_sync(self) -> dict[str, Any]:
        """Fetch current DPS values synchronously."""
        device = None
        try:
            device = self._create_device()
            response = device.status()
        except Exception as err:  # noqa: BLE001
            raise EufyRoboVacLocalApiError(
                f"Failed reading DPS from {self.host}: {err}"
            ) from err
        finally:
            if device is not None:
                _close = getattr(device, "close", None)
                if callable(_close):
                    _close()

        if not isinstance(response, dict):
            return {}

        dps = response.get("dps")
        if not isinstance(dps, dict):
            data = response.get("data")
            if isinstance(data, dict):
                nested_dps = data.get("dps")
                if isinstance(nested_dps, dict):
                    dps = nested_dps

        if not isinstance(dps, dict):
            _LOGGER.debug("No DPS payload in response for %s: %s", self.host, response)
            return {}

        return {str(key): value for key, value in dps.items()}

    async def async_get_dps(self, hass: HomeAssistant) -> dict[str, Any]:
        """Fetch current DPS values asynchronously."""
        return await hass.async_add_executor_job(self._get_dps_sync)
