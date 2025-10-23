"""API wrapper for DayBetter Services."""

from __future__ import annotations

from typing import Any

try:
    from daybetter_python import DayBetterClient
except ImportError:  # pragma: no cover
    DayBetterClient = None


class DayBetterApi:
    """Wrapper for DayBetter API client."""

    def __init__(self, token: str | None = None) -> None:
        """Initialize API with token."""
        if DayBetterClient is None:
            self._client = None
            self._token = None
            return

        self._token = token
        if token:
            self._client = DayBetterClient(token=token)
        else:
            self._client = DayBetterClient(token="")

    async def integrate(self, user_code: str) -> dict[str, Any]:
        """Create integration and get token using user code."""
        if self._client is None:
            raise RuntimeError("DayBetter client not available")

        result = await self._client.integrate(hass_code=user_code)

        if result and result.get("code") == 1 and DayBetterClient is not None:
            data = result.get("data", {})
            if "hassCodeToken" in data:
                self._token = data["hassCodeToken"]
                self._client = DayBetterClient(token=self._token)

        return result

    async def fetch_devices(self) -> list[dict[str, Any]]:
        """Fetch all devices."""
        if self._client is None:
            return []

        try:
            result = await self._client.fetch_devices()

            if isinstance(result, list):
                return result

            if isinstance(result, dict) and result.get("code") == 1:
                return result.get("data", [])
        except Exception:  # noqa: BLE001
            pass

        return []

    async def fetch_pids(self) -> dict[str, Any]:
        """Fetch all PIDs."""
        if self._client is None:
            return {}

        try:
            result = await self._client.fetch_pids()

            if isinstance(result, dict) and "light" in result and "sensor" in result:
                return result

            if isinstance(result, dict) and result.get("code") == 1:
                return result.get("data", {})
        except Exception:  # noqa: BLE001
            pass

        return {}

    async def fetch_device_statuses(self) -> list[dict[str, Any]]:
        """Fetch device statuses."""
        if self._client is None:
            return []

        try:
            result = await self._client.fetch_device_statuses()

            if isinstance(result, list):
                return result

            if isinstance(result, dict) and result.get("code") == 1:
                return result.get("data", [])
        except Exception:  # noqa: BLE001
            pass

        return []

    def filter_sensor_devices(
        self,
        devices: list[dict[str, Any]],
        pids: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Filter devices to only include sensors based on PID."""
        sensor_pids_str = pids.get("sensor", "")
        if not sensor_pids_str:
            return []

        sensor_pids = {pid.strip() for pid in sensor_pids_str.split(",")}

        return [
            device
            for device in devices
            if device.get("deviceMoldPid", "") in sensor_pids
        ]

    def merge_device_status(
        self,
        devices: list[dict[str, Any]],
        statuses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge device info with status info."""
        status_dict = {status.get("deviceName"): status for status in statuses}

        merged = []
        for device in devices:
            device_name = device.get("deviceName")
            merged_device = device.copy()

            if device_name in status_dict:
                merged_device.update(status_dict[device_name])

            merged.append(merged_device)

        return merged

    @property
    def token(self) -> str | None:
        """Return current token."""
        return self._token

    async def close(self) -> None:
        """Close the client session."""
        if self._client is not None:
            await self._client.close()
