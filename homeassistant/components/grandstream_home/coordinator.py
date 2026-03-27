"""Data update coordinator for Grandstream devices."""

from datetime import timedelta
import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    COORDINATOR_ERROR_THRESHOLD,
    COORDINATOR_UPDATE_INTERVAL,
    DEVICE_TYPE_GNS_NAS,
    DOMAIN,
    SIP_STATUS_MAP,
)

_LOGGER = logging.getLogger(__name__)


class GrandstreamCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Grandstream device."""

    last_update_method: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        device_type: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            device_type: Type of the device
            entry: Configuration entry

        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )
        self.device_type = device_type
        self.entry_id = entry.entry_id
        self._error_count = 0
        self._max_errors = COORDINATOR_ERROR_THRESHOLD

    def _process_status(self, status_data: str | dict) -> str:
        """Process status data and ensure it doesn't exceed maximum length.

        Args:
            status_data: Raw status data (string or dict)

        Returns:
            str: Processed status string

        """
        if not status_data:
            return "unknown"

        # If it's a dict, extract status field
        if isinstance(status_data, dict):
            status_data = status_data.get("status", str(status_data))

        # If it's a JSON string, try to parse it
        if isinstance(status_data, str) and status_data.startswith("{"):
            try:
                status_dict = json.loads(status_data)
                status_data = status_dict.get("status", status_data)
            except json.JSONDecodeError:
                pass

        # Convert to string and normalize
        status_str = str(status_data).lower().strip()

        # If status string is too long, truncate it
        if len(status_str) > 250:
            _LOGGER.warning(
                "Status string too long (%d characters), will be truncated",
                len(status_str),
            )
            return status_str[:250] + "..."

        return status_str

    def _get_api(self):
        """Get API instance from runtime_data or hass.data.

        Returns:
            API instance or None

        """
        # Try to get API from runtime_data first
        config_entry = None
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id == self.entry_id:
                config_entry = entry
                break

        api = None
        if (
            config_entry
            and hasattr(config_entry, "runtime_data")
            and config_entry.runtime_data
        ):
            api = config_entry.runtime_data.get("api")

        # Fallback to hass.data if runtime_data not available
        if not api:
            api = self.hass.data[DOMAIN][self.entry_id].get("api")

        return api

    def _handle_error(self, error_type: str) -> dict[str, Any]:
        """Handle error and return appropriate status.

        Args:
            error_type: Type of status key ("phone_status" or "device_status")

        Returns:
            Status dictionary

        """
        self._error_count += 1
        if self._error_count >= self._max_errors:
            return {error_type: "unavailable"}
        return {error_type: "unknown"}

    def _build_sip_account_dict(self, account: dict[str, Any]) -> dict[str, Any]:
        """Build SIP account dictionary with status mapping.

        Args:
            account: Raw account data

        Returns:
            Processed account dictionary

        """
        account_id = account.get("id", "")
        sip_id = account.get("sip_id", "")
        name = account.get("name", "")
        reg_status = account.get("reg", -1)
        status_text = SIP_STATUS_MAP.get(reg_status, f"Unknown ({reg_status})")

        return {
            "id": account_id,
            "sip_id": sip_id,
            "name": name,
            "reg": reg_status,
            "status": status_text,
        }

    def _process_push_data(self, data: dict[str, Any] | str) -> dict[str, Any]:
        """Process push data into standardized format.

        Args:
            data: Raw push data (dict or string)

        Returns:
            Processed data dictionary

        """
        # If data is a string, try to parse it as a dictionary
        if isinstance(data, str):
            try:
                parsed_data = json.loads(data)
                data = parsed_data
            except json.JSONDecodeError:
                data = {"phone_status": data}

        # At this point, data should be a dict
        if not isinstance(data, dict):
            data = {"phone_status": str(data)}

        # If data is a dict but doesn't have phone_status key, try to get from status or state
        if "phone_status" not in data:
            status = data.get("status") or data.get("state") or data.get("value")
            if status:
                data = {"phone_status": status}

        # Process status data
        if "phone_status" in data:
            data["phone_status"] = self._process_status(data["phone_status"])

        return data

    async def _fetch_gns_metrics(self, api) -> dict[str, Any]:
        """Fetch GNS NAS metrics.

        Args:
            api: API instance

        Returns:
            Device metrics data

        """
        result = await self.hass.async_add_executor_job(api.get_system_metrics)
        if not isinstance(result, dict):
            _LOGGER.error("API call failed (GNS metrics): %s", result)
            return self._handle_error("device_status")

        self._error_count = 0
        self.last_update_method = "poll"
        result.setdefault("device_status", "online")

        # Update device firmware version if available
        device = self.hass.data[DOMAIN][self.entry_id].get("device")
        if device and result.get("product_version"):
            device.set_firmware_version(result["product_version"])

        return result

    async def _fetch_sip_accounts(self, api) -> list[dict[str, Any]]:
        """Fetch SIP account status.

        Args:
            api: API instance

        Returns:
            List of SIP account data

        """
        sip_accounts: list[dict[str, Any]] = []
        try:
            sip_result = await self.hass.async_add_executor_job(api.get_accounts)
            if isinstance(sip_result, dict) and sip_result.get("response") == "success":
                sip_body = sip_result.get("body", [])
                # Body should be a list of SIP accounts
                if isinstance(sip_body, list):
                    sip_accounts.extend(
                        self._build_sip_account_dict(account)
                        for account in sip_body
                        if isinstance(account, dict)
                    )
                    _LOGGER.debug("SIP accounts retrieved: %s", sip_accounts)
                elif isinstance(sip_body, dict):
                    # Fallback: single account as dict
                    sip_accounts.append(self._build_sip_account_dict(sip_body))
        except (RuntimeError, ValueError, OSError) as e:
            _LOGGER.debug("Failed to get SIP status: %s", e)

        return sip_accounts

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint (polling).

        Returns:
            dict: Updated device data

        """
        try:
            # Get API instance
            api = self._get_api()
            if not api:
                _LOGGER.error("API not available")
                return self._handle_error("phone_status")

            # Check if HA control is disabled on device side
            if hasattr(api, "is_ha_control_disabled") and api.is_ha_control_disabled:
                _LOGGER.warning("HA control is disabled on device")
                return self._handle_error("phone_status")

            # GNS NAS metrics branch
            if self.device_type == DEVICE_TYPE_GNS_NAS and hasattr(
                api, "get_system_metrics"
            ):
                return await self._fetch_gns_metrics(api)

            # Default phone status branch
            result = await self.hass.async_add_executor_job(api.get_phone_status)
            if not isinstance(result, dict) or result.get("response") != "success":
                error_msg = (
                    result.get("body") if isinstance(result, dict) else str(result)
                )
                _LOGGER.error("API call failed: %s", error_msg)
                return self._handle_error("phone_status")

            self._error_count = 0
            status = result.get("body", "unknown")
            processed_status = self._process_status(status) + " "
            _LOGGER.info("Device status updated: %s", processed_status)
            self.last_update_method = "poll"

            # Get SIP account status
            sip_accounts = await self._fetch_sip_accounts(api)

            # Update device firmware version if available
            device = self.hass.data[DOMAIN][self.entry_id].get("device")
            if device and api.version:
                device.set_firmware_version(api.version)

        except (RuntimeError, ValueError, OSError, KeyError) as e:
            _LOGGER.error("Error getting device status: %s", e)
            error_result = self._handle_error("phone_status")
            error_result["sip_accounts"] = []
            return error_result
        return {"phone_status": processed_status, "sip_accounts": sip_accounts}

    async def async_handle_push_data(self, data: dict[str, Any]) -> None:
        """Handle pushed data.

        Args:
            data: Pushed data from device

        """
        try:
            _LOGGER.debug("Received push data: %s", data)
            data = self._process_push_data(data)
            self.last_update_method = "push"
            self.async_set_updated_data(data)
        except Exception as e:
            _LOGGER.error("Error processing push data: %s", e)
            raise

    def handle_push_data(self, data: dict[str, Any]) -> None:
        """Handle push data synchronously.

        Args:
            data: Pushed data from device

        """
        try:
            _LOGGER.debug("Processing sync push data: %s", data)
            data = self._process_push_data(data)
            self.last_update_method = "push"
            self.async_set_updated_data(data)
        except Exception as e:
            _LOGGER.error("Error processing sync push data: %s", e)
            raise
