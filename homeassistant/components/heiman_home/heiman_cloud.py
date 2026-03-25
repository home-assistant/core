"""Heiman Cloud HTTP API Client with OAuth2 Support.

Handles HTTP communication with Heiman Cloud API for authentication,
device discovery, and management using OAuth2 Authorization Code Flow.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import os
import time
from typing import Any

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_API_URL,
    CONF_HOME_ID,
    CONF_REFRESH_TOKEN,
    CONF_REGION,
    CONF_SECURE_ID,
    CONF_SECURE_KEY,
    CONF_TOKEN_EXPIRES_TS,
    CONF_USER_ID,
    DEFAULT_REGION,
    DOMAIN,
    OAUTH2_CLIENT_ID,
    OAUTH2_REDIRECT_URL,
    REGIONS,
)
from .heiman_error import HeimanError, HeimanErrorCode
from .heiman_oauth import HeimanHttpClient, HeimanOauthClient
from .token_refresh import TokenRefreshManager

_LOGGER = logging.getLogger(__name__)

# Token refresh margin (70% of expires_in)
TOKEN_EXPIRES_TS_RATIO = 0.7


def _load_json_file(file_path: str) -> dict:
    """Load a JSON file from disk."""
    with open(file_path, encoding="utf-8") as file_handle:
        return json.load(file_handle)


class HeimanCloudClient:
    """Heiman Cloud API client with OAuth2 support."""

    def __init__(
        self,
        hass,
        entry_id: str,
        config: dict,
        persistent_notify: Callable[[str, str | None, str | None], None] | None = None,
    ) -> None:
        """Initialize cloud client with OAuth2."""
        self._hass = hass
        self._entry_id = entry_id
        self._config = config
        self._persistent_notify = persistent_notify

        # Get region settings
        region = config.get(CONF_REGION, DEFAULT_REGION)
        self._region_config = REGIONS.get(region) or REGIONS.get(DEFAULT_REGION)

        self._api_url = config.get(CONF_API_URL, self._region_config.get("api_url"))
        self._user_id = config.get(CONF_USER_ID)
        self._home_id = config.get(CONF_HOME_ID)

        # OAuth2 tokens
        self._access_token = config.get(CONF_ACCESS_TOKEN)
        self._refresh_token = config.get(CONF_REFRESH_TOKEN)
        self._token_expires_ts = config.get(CONF_TOKEN_EXPIRES_TS, 0)

        # Secure credentials for MQTT
        self._secure_id = config.get(CONF_SECURE_ID, "")
        self._secure_key = config.get(CONF_SECURE_KEY, "")

        # OAuth2 and HTTP clients
        self._oauth_client: HeimanOauthClient | None = None
        self._http_client: HeimanHttpClient | None = None

        # Cached data
        self._home_info: dict | None = None
        self._devices: dict[str, dict] = {}
        self._all_devices: dict[str, dict] = {}  # All devices across all homes

        # MQTT client (set after initialization)
        self.mqtt_client = None

        # Token refresh manager
        self._token_refresh_manager: TokenRefreshManager | None = None

        # Event loop
        self._loop = asyncio.get_running_loop()

    async def _init_oauth_client(self) -> None:
        """Initialize OAuth2 client."""
        if not self._oauth_client:
            _LOGGER.debug("Initializing OAuth2 client...")
            _LOGGER.debug("Client ID: %s", OAUTH2_CLIENT_ID)
            _LOGGER.debug("Redirect URL: %s", OAUTH2_REDIRECT_URL)
            _LOGGER.debug("Region config: %s", self._region_config)

            self._oauth_client = HeimanOauthClient(
                client_id=OAUTH2_CLIENT_ID,
                redirect_url=OAUTH2_REDIRECT_URL,
                cloud_server=self._region_config.get("name", "cn"),
                region_config=self._region_config,
                loop=self._loop,
            )

            _LOGGER.debug("OAuth2 client initialized successfully")

    async def async_initialize_http_client(self) -> None:
        """Initialize HTTP client with current access token."""
        if not self._http_client and self._access_token:
            _LOGGER.debug("Initializing HTTP client...")
            _LOGGER.debug("API URL: %s", self._api_url)
            _LOGGER.debug("Client ID: %s", OAUTH2_CLIENT_ID)
            _LOGGER.debug(
                "Access token (first 20 chars): %s...",
                self._access_token[:20],
            )

            self._http_client = HeimanHttpClient(
                api_url=self._api_url,
                client_id=OAUTH2_CLIENT_ID,
                access_token=self._access_token,
                loop=self._loop,
            )

            _LOGGER.debug("HTTP client initialized successfully")
        elif not self._access_token:
            _LOGGER.warning("Cannot initialize HTTP client: no access token")
        else:
            _LOGGER.debug("HTTP client already initialized")

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Return the current refresh token."""
        return self._refresh_token

    @property
    def token_expires_ts(self) -> int:
        """Return the token expiry timestamp."""
        return self._token_expires_ts

    @property
    def persistent_notify(self) -> Callable[[str, str | None, str | None], None] | None:
        """Return the persistent notification callback."""
        return self._persistent_notify

    def check_token_expiry(self, margin_seconds: int = 300) -> bool:
        """Check if access token is expired or near expiry."""
        return self._check_token_expiry(margin_seconds)

    async def refresh_token_if_needed(self) -> None:
        """Refresh access token if expired."""
        await self._refresh_token_if_needed()

    def _check_token_expiry(self, margin_seconds: int = 300) -> bool:
        """Check if access token is expired or near expiry.

        Args:
            margin_seconds: Safety margin in seconds (default: 5 minutes)

        Returns:
            True if expired or will expire within margin, False otherwise
        """
        if not self._token_expires_ts:
            return True

        current_time = int(time.time())
        time_to_expiry = self._token_expires_ts - current_time

        # Return True if expired or will expire within safety margin
        is_expired = current_time >= self._token_expires_ts
        is_near_expiry = time_to_expiry <= margin_seconds

        if is_expired:
            _LOGGER.debug("Token has expired")
        elif is_near_expiry:
            _LOGGER.debug(
                "Token will expire in %.1f minutes (threshold: %d minutes)",
                time_to_expiry / 60,
                margin_seconds // 60,
            )

        return is_expired or is_near_expiry

    async def _refresh_token_if_needed(self) -> None:
        """Refresh access token if expired."""
        if not self._refresh_token:
            raise HeimanError(
                "No refresh token available",
                HeimanErrorCode.CODE_OAUTH_INVALID_REFRESH_TOKEN,
            )

        # Check token status with 5-minute safety margin
        if not self._check_token_expiry(margin_seconds=300):
            _LOGGER.debug(
                "Token is still valid (expires at %s), no refresh needed",
                self._token_expires_ts,
            )
            return

        _LOGGER.info("Access token expired or near expiry, refreshing...")

        try:
            await self._init_oauth_client()

            new_tokens = await self._oauth_client.refresh_access_token_async(
                refresh_token=self._refresh_token,
            )

            # Update tokens
            self._access_token = new_tokens.get("access_token")
            self._refresh_token = new_tokens.get("refresh_token")
            self._token_expires_ts = new_tokens.get("expires_ts")

            # Update HTTP client with new token
            if self._http_client:
                self._http_client.update_http_header(access_token=self._access_token)

            _LOGGER.info(
                "Token refreshed successfully, expires at: %s",
                self._token_expires_ts,
            )

            # Update config in Hass data
            self._hass.data[DOMAIN][self._entry_id].update(
                {
                    CONF_ACCESS_TOKEN: self._access_token,
                    CONF_REFRESH_TOKEN: self._refresh_token,
                    CONF_TOKEN_EXPIRES_TS: self._token_expires_ts,
                },
            )

            # Schedule config entry update
            try:
                entry = self._hass.config_entries.async_get_entry(self._entry_id)
                if entry:
                    new_data = dict(entry.data)
                    new_data.update(
                        {
                            CONF_ACCESS_TOKEN: self._access_token,
                            CONF_REFRESH_TOKEN: self._refresh_token,
                            CONF_TOKEN_EXPIRES_TS: self._token_expires_ts,
                        },
                    )
                    self._hass.config_entries.async_update_entry(entry, data=new_data)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Failed to save updated token: %s", err)

        except Exception as err:
            _LOGGER.error("Token refresh failed: %s", err)
            _LOGGER.error("Error type: %s", type(err).__name__)

            # Check if it's a JSON decode error (empty response)
            if "json decode error" in str(err).lower():
                _LOGGER.error("API returned empty or invalid response")
                _LOGGER.error(
                    "This usually means the refresh token has expired or is invalid",
                )
                raise HeimanError(
                    "Token refresh failed: Invalid or expired refresh token. Please re-authenticate.",
                    HeimanErrorCode.CODE_OAUTH_INVALID_REFRESH_TOKEN,
                ) from err

            # Check if it's an authentication error
            if any(
                code in str(err) for code in ["401", "unauthorized", "invalid_token"]
            ):
                _LOGGER.error("Authentication failed during token refresh")
                raise HeimanError(
                    "Token refresh failed: Authentication failed. Please re-authenticate.",
                    HeimanErrorCode.CODE_OAUTH_UNAUTHORIZED,
                ) from err

                # Generic error
                raise HeimanError(
                    f"Token refresh failed: {err}",
                    HeimanErrorCode.CODE_OAUTH_INVALID_REFRESH_TOKEN,
                ) from err

    async def start_token_refresh(self) -> None:
        """Start automatic token refresh."""
        if not self._token_refresh_manager:
            self._token_refresh_manager = TokenRefreshManager(
                hass=self._hass,
                entry_id=self._entry_id,
                cloud_client=self,
                on_token_refreshed=self._on_token_refreshed,
            )
            await self._token_refresh_manager.start_async()
            _LOGGER.info("Token auto-refresh started")

    async def stop_token_refresh(self) -> None:
        """Stop automatic token refresh."""
        if self._token_refresh_manager:
            await self._token_refresh_manager.stop_async()
            self._token_refresh_manager = None
            _LOGGER.debug("Token auto-refresh stopped")

    def _on_token_refreshed(self, token_data: dict[str, Any]) -> None:
        """Callback when token is refreshed.

        Args:
            token_data: Dictionary containing new token information
        """
        _LOGGER.debug("Token refreshed callback called")
        # Update config in Hass data
        self._hass.data[DOMAIN][self._entry_id].update(token_data)

    async def async_login(self) -> dict:
        """Login to Heiman Cloud via OAuth2.

        This method is kept for backward compatibility but OAuth2
        authentication should be done via config flow.
        """
        _LOGGER.warning("async_login called, use OAuth2 flow instead")
        return {
            "access_token": self._access_token,
            "user_id": self._user_id,
        }

    async def _make_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict | list | None = None,
        params: dict | None = None,
        skip_token_check: bool = False,
    ) -> Any:
        """Make an authenticated API request with auto token refresh."""
        # Refresh token if needed
        if not skip_token_check:
            await self._refresh_token_if_needed()

        # Initialize HTTP client
        await self.async_initialize_http_client()

        try:
            if method == "GET":
                result = await self._http_client.api_get_async(
                    path=endpoint,
                    params=params,
                )
            else:
                # Support both dict and list request bodies
                request_data = data if data is not None else {}
                result = await self._http_client.api_post_async(
                    path=endpoint,
                    data=request_data,
                )

        except HeimanError as err:
            # Check if it's a token error
            if err.error_code in [
                HeimanErrorCode.CODE_HTTP_UNAUTHORIZED,
                HeimanErrorCode.CODE_HTTP_INVALID_ACCESS_TOKEN,
            ]:
                _LOGGER.warning("Received unauthorized error, forcing token refresh")
                # Force token refresh
                self._token_expires_ts = 0
                await self._refresh_token_if_needed()
                # Retry request
                return await self._make_api_request(
                    endpoint=endpoint,
                    method=method,
                    data=data,
                    params=params,
                    skip_token_check=True,
                )
            raise
        else:
            return result

    async def async_get_homes(self) -> list[dict]:
        """Get list of homes for user."""
        if not self._user_id:
            _LOGGER.error("User ID not available for getting homes")
            return []

        _LOGGER.debug("=" * 80)
        _LOGGER.debug("Fetching homes from cloud API")
        _LOGGER.debug("=" * 80)
        _LOGGER.debug(">>> User ID: %s", self._user_id)
        _LOGGER.debug(
            ">>> HTTP client status: %s",
            "initialized" if self._http_client else "NOT initialized",
        )

        try:
            result = await self._make_api_request(
                endpoint="/api-app/homeUserRelation/get/homeList",
                method="POST",
                data={"userId": self._user_id},
            )

            _LOGGER.debug(">>> Homes API response type: %s", type(result))
            _LOGGER.debug(
                ">>> Homes API response (first 1000 chars): %s",
                str(result)[:1000],
            )

            # _make_api_request already extracts the 'result' field from the API response
            # The API returns: {status: 200, result: [...], message: "...", timestamp: ...}
            # So result should already be a list of homes
            if isinstance(result, list):
                homes = result
                _LOGGER.debug(
                    ">>> Response is already a list with %s items",
                    len(homes),
                )
            elif isinstance(result, dict):
                # Check if result is wrapped in another dict
                if "result" in result and isinstance(result["result"], list):
                    homes = result["result"]
                    _LOGGER.debug(
                        ">>> Extracted list from 'result' key: %s items",
                        len(homes),
                    )
                else:
                    _LOGGER.warning(
                        ">>> Unexpected dict format, trying to extract homes",
                    )
                    homes = []
                    # Try to find a list field
                    for key, value in result.items():
                        if isinstance(value, list):
                            _LOGGER.debug(
                                ">>> Found list field '%s' with %s items",
                                key,
                                len(value),
                            )
                            homes = value
                            break
            else:
                _LOGGER.warning(">>> Unexpected result format: %s", type(result))
                homes = []

            if isinstance(homes, list) and homes:
                _LOGGER.info(
                    ">>> Found %s homes for user %s",
                    len(homes),
                    self._user_id,
                )
                for idx, home in enumerate(homes):
                    _LOGGER.debug(
                        ">>> Home %d: %s",
                        idx + 1,
                        {
                            k: v
                            for k, v in home.items()
                            if k in ["homeId", "homeName", "deviceCount"]
                        },
                    )
            else:
                _LOGGER.warning(">>> No homes found or invalid format")
                _LOGGER.warning(">>> Final homes value: %s", homes)
                homes = []

            _LOGGER.info("Found %s homes for user %s", len(homes), self._user_id)
        except Exception as err:
            _LOGGER.error("=" * 80)
            _LOGGER.error("Failed to get homes!")
            _LOGGER.error("=" * 80)
            _LOGGER.error("Error type: %s", type(err).__name__)
            _LOGGER.error("Error message: %s", str(err))
            _LOGGER.error("")
            _LOGGER.exception("Full traceback")
            _LOGGER.error("=" * 80)
            return []
        else:
            return homes

    def set_home(self, home_id: str) -> None:
        """Set current home ID."""
        self._home_id = home_id
        _LOGGER.info("Set home ID: %s", home_id)

    async def async_get_devices(self) -> dict[str, dict]:
        """Get list of devices in current home."""
        _LOGGER.debug(
            "async_get_devices called: home_id=%s, user_id=%s",
            self._home_id,
            self._user_id,
        )

        if not self._home_id:
            _LOGGER.error("Home ID not set (current value: %s)", self._home_id)
            return {}

        if not self._user_id:
            _LOGGER.error(
                "User ID not available for getting devices (current value: %s)",
                self._user_id,
            )
            return {}

        try:
            # Use pagination API to get devices
            # Request structure: {help: {pageSize, pageNumber}, custom: {homeId, propertyIdentifiers, secureId, userId}}
            request_data = {
                "help": {"pageSize": 100, "pageNumber": 1},
                "custom": {
                    "homeId": self._home_id,
                    "propertyIdentifiers": [
                        "ArmModeControl",
                        "GatewayHandleStatus",
                        "GasSensorState",
                        "Alarm",
                        "RingSwitch",
                        "LockState",
                        "AlarmSwitch",
                        "LightSwitch",
                        "BWY",
                        "SWY",
                        "PowerSwitch_1",
                        "PowerSwitch_2",
                        "PowerSwitch_3",
                        "CurtainPosition",
                        "PowerSwitch",
                        "RealTimePower",
                        "SmokeSensorState",
                        "CurrentTemperature",
                        "CurrentHumidity",
                        "TamperState",
                        "SwitchState",
                        "alarmEnable",
                        "WaterSensorState",
                        "FreezingPointAlarm",
                        "PM25",
                        "PM10",
                        "co2",
                        "OF",
                        "ON",
                        "GatewayMac",
                        "Icon",
                        "UserName",
                        "HeatSensorStatus",
                        "BatteryPercentage",
                        "UnderVoltError",
                        "MasterDevice",
                        "LocalSceneControl",
                        "outdoorTemperature",
                        "SensorLifeStatus",
                        "TempAlarmType",
                        "HumiAlarmType",
                        "TempShowType",
                        "HumidityShowType",
                        "MainPowerStatus",
                        "MotionAlarmState",
                        "ContactState",
                        "BrightnessLevel",
                        "Volume",
                        "RGBColor",
                        "RingOption",
                        "PlayRing",
                        "peopleState",
                        "activeState",
                        "alarmType",
                        "peopleStateSwitch",
                        "activeStateSwitch",
                        "battery_value",
                        "faultSta",
                        "alarmSta",
                        "CertificationType",
                        "coValue",
                        "CONC",
                        "GAS",
                    ],
                    "secureId": self._secure_id,
                    "userId": self._user_id,
                },
            }

            result = await self._make_api_request(
                endpoint="/api-app/device/get/listByPage",
                method="POST",
                data=request_data,
            )

            # API returns {status, result: {pageIndex, pageSize, total, data: [...]}, message, timestamp}
            # _make_api_request/_api_post_async already extracts the 'result' field
            # So result is already {pageIndex, pageSize, total, data: [...]}
            _LOGGER.debug("API response type: %s", type(result))
            _LOGGER.debug(
                "API response keys: %s",
                list(result.keys()) if isinstance(result, dict) else "N/A",
            )

            if isinstance(result, dict):
                # result is already the 'result' object from API response
                result_data = result
                _LOGGER.debug("result_data type: %s", type(result_data))
                devices = (
                    result_data.get("data", []) if isinstance(result_data, dict) else []
                )
            else:
                _LOGGER.warning("API returned non-dict result: %s", type(result))
                devices = []

            # Translate product names and index by device id
            translated_devices = []
            for device in devices:
                translated_device = await self._translate_product_name(device)
                translated_devices.append(translated_device)

            # Index by device id (note: API uses 'id' field, not 'deviceId')
            self._devices = (
                {d.get("id"): d for d in translated_devices}
                if isinstance(translated_devices, list)
                else {}
            )

            if isinstance(translated_devices, list):
                device_count = len(self._devices)
                api_total = result_data.get("total", 0)

                _LOGGER.info(
                    "Found %s/%s devices in home %s",
                    device_count,
                    api_total,
                    self._home_id,
                )
                # Remove frequency suffixes like (915MHz) or (868MHz) from model name
                # Log details of first few devices
                for idx, device in enumerate(translated_devices[:5]):
                    _LOGGER.debug(
                        "Device %d: id=%s, name=%s, deviceName=%s, productName=%s, state=%s",
                        idx,
                        device.get("id"),
                        device.get("name"),
                        device.get("deviceName"),
                        device.get("productName"),
                        device.get("state", {}).get("text")
                        if isinstance(device.get("state"), dict)
                        else device.get("state"),
                    )
                if len(translated_devices) > 5:
                    _LOGGER.debug(
                        "... and %s more devices",
                        len(translated_devices) - 5,
                    )

                # Check if API total matches actual data count
                total_from_api = result_data.get("total", 0)
                if len(translated_devices) != total_from_api:
                    _LOGGER.warning(
                        "WARNING: API reports %s total devices but returned only %s devices in data array",
                        total_from_api,
                        len(translated_devices),
                    )
                    _LOGGER.warning(
                        "This might be a pagination issue or some devices are filtered out",
                    )
            else:
                _LOGGER.warning(
                    "Unexpected devices format: %s",
                    type(translated_devices),
                )

        except Exception as err:
            _LOGGER.error("Failed to get devices: %s", err)
            _LOGGER.error("Exception type: %s", type(err).__name__)
            _LOGGER.error("Home ID: %s, User ID: %s", self._home_id, self._user_id)
            _LOGGER.exception("Traceback")
            return {}
        else:
            return self._devices

    async def _translate_product_name(self, device: dict) -> dict:
        """Translate product name based on product ID.

        Args:
            device: Device info dict from API

        Returns:
            Updated device dict with translated productName
        """
        product_id = device.get("productId", "")
        original_product_name = device.get("productName", "")

        if not product_id:
            return device

        # Try to get translation from translations JSON files
        try:
            # Get integration language from config
            integration_language = self._config.get("integration_language", "zh-Hans")

            # Map language codes to translation file names
            lang_map = {
                "de": "de.json",
                "en": "en.json",
                "es": "es.json",
                "fr": "fr.json",
                "it": "it.json",
                "ja": "ja.json",
                "nl": "nl.json",
                "pt": "pt.json",
                "pt-BR": "pt-BR.json",
                "ru": "ru.json",
                "tr": "tr.json",
                "zh-Hans": "zh-Hans.json",
                "zh-Hant": "zh-Hant.json",
            }

            lang_file = lang_map.get(integration_language, "zh-Hans.json")

            translations_file = os.path.join(
                os.path.dirname(__file__),
                "translations",
                lang_file,
            )

            if os.path.exists(translations_file):
                translations = await asyncio.to_thread(
                    _load_json_file,
                    translations_file,
                )

                # Look up product_type translation
                product_types = translations.get("product_type", {})
                translated_name = product_types.get(product_id)

                if translated_name:
                    # Translation found, update device info
                    device["productName"] = translated_name
                    _LOGGER.debug(
                        "Translated product %s: '%s' -> '%s' (language: %s)",
                        product_id,
                        original_product_name,
                        translated_name,
                        integration_language,
                    )
                else:
                    # No translation found, keep original
                    _LOGGER.debug(
                        "No translation for product %s, keeping original: '%s'",
                        product_id,
                        original_product_name,
                    )
            else:
                _LOGGER.warning("Translation file not found: %s", translations_file)

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to translate product name for %s: %s",
                product_id,
                err,
            )

        return device

    async def async_get_device_info(self, device_id: str) -> dict | None:
        """Get device information."""
        try:
            result = await self._make_api_request(
                endpoint="/api-app/device/get/info",
                method="GET",
                params={"deviceId": device_id},
            )

            # API returns {status, result: {...}, message, timestamp}
            if isinstance(result, dict):
                return (
                    result.get("result")
                    if isinstance(result.get("result"), dict)
                    else None
                )
            return result if isinstance(result, dict) else None

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to get device info for %s: %s", device_id, err)
            return None

    async def async_get_device_instance_detail(self, device_id: str) -> dict | None:
        """Get device instance detail via /api-saas/device-instance/{device_id}/detail.

        Args:
            device_id: The device ID

        Returns:
            Device detail dict containing metadata field, or None on error
        """
        if not device_id:
            _LOGGER.error("Device ID is empty for getting device instance detail")
            return None

        try:
            endpoint = f"/api-saas/device-instance/{device_id}/detail"
            result = await self._make_api_request(endpoint=endpoint, method="GET")
            # _make_api_request already extracts the 'result' field
            # Response should be: {metadata: "{...}", productName: "...", deviceType: {...}, state: {...}}
            if isinstance(result, dict):
                _LOGGER.debug(
                    "Got device instance detail for %s: keys=%s",
                    device_id,
                    list(result.keys()),
                )
                return result
            _LOGGER.warning(
                "Unexpected device instance detail response type for %s: %s",
                device_id,
                type(result),
            )
        except Exception:
            _LOGGER.exception(
                "Failed to get device instance detail for %s",
                device_id,
            )
            return None
        else:
            return None

    async def async_get_device_detail(self, device_id: str) -> dict | None:
        """Get device detail via /api-saas/device/instance/app/11/{device_id}/detail.

        Args:
            device_id: The device ID

        Returns:
            Device detail dict containing deriveMetadata field, or None on error
        """
        if not device_id:
            _LOGGER.error("Device ID is empty for getting device detail")
            return None

        try:
            endpoint = f"/api-saas/device/instance/app/11/{device_id}/detail"
            result = await self._make_api_request(endpoint=endpoint, method="GET")
            # _make_api_request already extracts the 'result' field
            # Response should be: {deriveMetadata: "...", ...}
            if isinstance(result, dict):
                _LOGGER.debug(
                    "Got device detail for %s: keys=%s",
                    device_id,
                    list(result.keys()),
                )
                return result
            _LOGGER.warning(
                "Unexpected device detail response type for %s: %s",
                device_id,
                type(result),
            )
        except Exception:
            _LOGGER.exception(
                "Failed to get device detail for %s",
                device_id,
            )
            return None
        else:
            return None

    async def async_get_device_panel(self, product_id: str) -> dict | None:
        """Get device panel information for a product.

        Args:
            product_id: The product ID to get panel for

        Returns:
            Panel info dict with fields like panelUrl, panelName, etc., or None
        """
        if not self._secure_id:
            _LOGGER.error("Secure ID not available for getting device panel")
            return None

        try:
            result = await self._make_api_request(
                endpoint="/api-app/panel/get/by/app/product",
                method="POST",
                data={"appId": self._secure_id, "idList": [product_id]},
            )

            # API returns {status, result: [...], message, timestamp}
            if isinstance(result, dict):
                panels = result.get("result", [])
                if isinstance(panels, list) and len(panels) > 0:
                    # Return first panel info
                    return panels[0]
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Failed to get device panel for product %s: %s",
                product_id,
                err,
            )
            return None
        else:
            return None

    async def async_get_device_alarms(
        self,
        device_id: str,
        home_id: str | None = None,
        page_size: int = 20,
        page_number: int = 1,
    ) -> dict:
        """Get alarm logs for a specific device.

        Args:
            device_id: The device ID (iotId in API)
            home_id: The home ID, defaults to current home if not provided
            page_size: Number of alarms per page (default: 20)
            page_number: Page number (default: 1)

        Returns:
            Dict with keys: pageIndex, pageSize, total, data (list of alarm records)
            Returns empty dict on error
        """
        target_home_id = home_id or self._home_id
        if not target_home_id:
            _LOGGER.error("Home ID not available for getting device alarms")
            return {}

        try:
            request_data = {
                "help": {"pageSize": page_size, "pageNumber": page_number},
                "custom": {"iotId": device_id, "homeId": target_home_id},
            }
            result = await self._make_api_request(
                endpoint="/api-app/message/center/push/message/_query",
                method="POST",
                data=request_data,
            )

            # _api_post_async already extracts the 'result' field from API response
            # So result is already {pageIndex, pageSize, total, data: [...]}
            if isinstance(result, dict) and "data" in result:
                _LOGGER.debug(
                    "Retrieved %s alarms for device %s (page %s/%s, total: %s)",
                    len(result.get("data", [])),
                    device_id,
                    result.get("pageIndex", page_number),
                    (result.get("total", 0) + result.get("pageSize", page_size) - 1)
                    // result.get("pageSize", page_size)
                    if result.get("pageSize", 0) > 0
                    else 1,
                    result.get("total", 0),
                )
                return result
            _LOGGER.warning("Unexpected alarm result format: %s", result)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to get device alarms for %s: %s", device_id, err)
            return {}
        else:
            return {}

    async def async_read_device_property(
        self,
        product_id: str,
        device_id: str,
        property_name: str,
    ) -> dict | None:
        """Read a device property via HTTP API.

        Uses /api-saas/dashboard/_multi endpoint to fetch device properties.

        Args:
            product_id: The product ID
            device_id: The device ID (iotId)
            property_name: The property name to read

        Returns:
            Dict with 'value' key containing the property value, or None on error
        """
        # Validate parameters to prevent 400 errors
        if not product_id:
            _LOGGER.debug(
                "Skipping property read: product_id is empty for device %s, property %s",
                device_id,
                property_name,
            )
            return None
        if not device_id:
            _LOGGER.debug(
                "Skipping property read: device_id is empty for property %s",
                property_name,
            )
            return None
        if not property_name:
            _LOGGER.debug("Skipping property read: property_name is empty")
            return None

        try:
            # Build request payload for multi-dashboard API
            # API expects a list directly as request body, not wrapped in a dict
            request_data = [
                {
                    "dashboard": "device",
                    "object": product_id,
                    "measurement": "properties",
                    "dimension": "history",
                    "params": {
                        "deviceId": device_id,
                        "history": 1,
                        "properties": [property_name],
                    },
                },
            ]

            _LOGGER.debug(
                "Reading device property: device_id=%s, product_id=%s, property=%s",
                device_id,
                product_id,
                property_name,
            )

            result = await self._make_api_request(
                endpoint="/api-saas/dashboard/_multi",
                method="POST",
                data=request_data,
            )

            # Parse the response
            # Response format: [{"data": {"value": {...}}, ...}, ...]
            if not isinstance(result, list):
                _LOGGER.debug(
                    "Unexpected response format for property read: %s",
                    type(result),
                )
                return None

            # Find the property value in the response
            for item in result:
                if not isinstance(item, dict):
                    continue
                data = item.get("data", {})
                if not isinstance(data, dict):
                    continue
                value_info = data.get("value", {})
                if not isinstance(value_info, dict):
                    continue

                # Check if this is the property we're looking for
                if value_info.get("property") == property_name:
                    # Extract the value based on type
                    prop_type = value_info.get("type", "")
                    extracted_value = None
                    if prop_type == "int":
                        extracted_value = value_info.get("numberValue")
                    elif prop_type == "enum":
                        # Try to parse as integer for enum values like "0", "1"
                        enum_value = value_info.get("value", "0")
                        try:
                            extracted_value = int(enum_value)
                        except ValueError, TypeError:
                            extracted_value = enum_value
                    else:
                        extracted_value = value_info.get("value")

                    # 规范化值类型：列表/字典转换为JSON字符串（传感器状态必须是字符串或数字）
                    # 空集合返回None避免HA数值转换错误
                    if isinstance(extracted_value, (list, dict)):
                        if len(extracted_value) == 0:
                            extracted_value = None
                        else:
                            try:
                                extracted_value = json.dumps(
                                    extracted_value,
                                    ensure_ascii=False,
                                )
                            except TypeError, ValueError:
                                extracted_value = str(extracted_value)

                    return {"value": extracted_value}

            _LOGGER.debug(
                "Property %s not found in response for device %s",
                property_name,
                device_id,
            )
        except HeimanError as err:
            # Handle specific Heiman API errors
            if err.error_code == HeimanErrorCode.CODE_HTTP_ERROR:
                # 400 errors usually indicate invalid request parameters
                # This can happen for devices that don't support certain properties
                _LOGGER.debug(
                    "HTTP error reading property %s for device %s: %s. "
                    "Device may not support this property.",
                    property_name,
                    device_id,
                    err,
                )
            else:
                _LOGGER.debug(
                    "API error reading property %s for device %s: %s",
                    property_name,
                    device_id,
                    err,
                )
            return None
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Failed to read device property %s for device %s: %s",
                property_name,
                device_id,
                err,
            )
            return None
        else:
            return None

    async def async_read_device_properties(
        self,
        product_id: str,
        device_id: str,
        property_names: list[str],
    ) -> dict[str, Any]:
        """批量读取设备属性（优化版）.

        通过一次 API 调用读取多个属性，减少网络请求次数。

        Args:
            product_id: 产品 ID
            device_id: 设备 ID (iotId)
            property_names: 属性名称列表，如 ['PowerSwitch', 'Brightness', 'ColorTemperature']

        Returns:
            Dict[str, Any]: 属性值字典，如 {'PowerSwitch': 1, 'Brightness': 80}
        """
        # 验证参数
        if not product_id:
            _LOGGER.debug(
                "Skipping batch property read: product_id is empty for device %s",
                device_id,
            )
            return {}
        if not device_id:
            _LOGGER.debug("Skipping batch property read: device_id is empty")
            return {}
        if not property_names:
            _LOGGER.debug(
                "Skipping batch property read: property_names is empty for device %s",
                device_id,
            )
            return {}

        try:
            # Build request payload for multi-dashboard API
            # 一次性请求所有属性
            request_data = [
                {
                    "dashboard": "device",
                    "object": product_id,
                    "measurement": "properties",
                    "dimension": "history",
                    "params": {
                        "deviceId": device_id,
                        "history": 1,
                        "properties": property_names,  # 批量请求所有属性
                    },
                },
            ]

            _LOGGER.debug(
                "批量读取设备属性: device_id=%s, product_id=%s, properties=%s",
                device_id,
                product_id,
                property_names,
            )

            result = await self._make_api_request(
                endpoint="/api-saas/dashboard/_multi",
                method="POST",
                data=request_data,
            )

            # 解析响应，返回属性字典
            # Response format: [{"data": {"value": {...}}, ...}, ...]
            properties = {}

            if not isinstance(result, list):
                _LOGGER.debug(
                    "Unexpected response format for batch property read: %s",
                    type(result),
                )
                return {}

            # 解析所有属性值
            for item in result:
                if not isinstance(item, dict):
                    continue
                data = item.get("data", {})
                if not isinstance(data, dict):
                    continue
                value_info = data.get("value", {})
                if not isinstance(value_info, dict):
                    continue

                # 提取属性名和值
                prop_name = value_info.get("property")
                if not prop_name or prop_name not in property_names:
                    continue

                # 根据类型提取值
                prop_type = value_info.get("type", "")
                extracted_value = None
                if prop_type == "int":
                    extracted_value = value_info.get("numberValue")
                elif prop_type == "enum":
                    enum_value = value_info.get("value", "0")
                    try:
                        extracted_value = int(enum_value)
                    except ValueError, TypeError:
                        extracted_value = enum_value
                else:
                    extracted_value = value_info.get("value")

                # 规范化值类型：列表/字典转换为JSON字符串（传感器状态必须是字符串或数字）
                # 空集合返回None避免HA数值转换错误
                if isinstance(extracted_value, (list, dict)):
                    if len(extracted_value) == 0:
                        extracted_value = None
                    else:
                        try:
                            extracted_value = json.dumps(
                                extracted_value,
                                ensure_ascii=False,
                            )
                        except TypeError, ValueError:
                            extracted_value = str(extracted_value)

                properties[prop_name] = extracted_value

            _LOGGER.debug(
                "批量读取属性成功: device_id=%s, 返回 %s/%s 个属性",
                device_id,
                len(properties),
                len(property_names),
            )
        except HeimanError as err:
            if err.error_code == HeimanErrorCode.CODE_HTTP_ERROR:
                _LOGGER.debug(
                    "HTTP error reading batch properties for device %s: %s",
                    device_id,
                    err,
                )
            else:
                _LOGGER.debug(
                    "API error reading batch properties for device %s: %s",
                    device_id,
                    err,
                )
            return {}
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Failed to read batch device properties for device %s: %s",
                device_id,
                err,
            )
            return {}
        else:
            return properties

    async def async_write_device_property(
        self,
        product_id: str,
        device_id: str,
        property_name: str,
        value: Any,
        device_info: dict | None = None,
    ) -> bool:
        """Write a device property via MQTT.

        Args:
            product_id: Device product ID
            device_id: Device ID
            property_name: Property name to write
            value: Value to write
            device_info: Optional device info for child device detection

        Returns:
            True if successful, False otherwise
        """
        if self.mqtt_client:
            return await self.mqtt_client.async_write_property(
                product_id=product_id,
                device_id=device_id,
                property_name=property_name,
                value=value,
                device_info=device_info,
            )
        return False

    @property
    def api_url(self) -> str | None:
        """Return the API URL."""
        return self._api_url

    @property
    def user_id(self) -> str | None:
        """Get user ID."""
        return self._user_id

    @property
    def user_display_name(self) -> str | None:
        """Get user display name (nickName if available, otherwise email)."""
        user_info = self._config.get("user_info", {})
        nick_name = user_info.get("nickName", "").strip()
        if nick_name:
            return nick_name
        email = user_info.get("email", "").strip()
        if email:
            return email
        return user_info.get("username") or self._user_id

    @property
    def home_id(self) -> str | None:
        """Get current home ID."""
        return self._home_id

    @property
    def devices(self) -> dict[str, dict]:
        """Get device list.

        Returns all devices across all homes if available,
        otherwise returns devices from current home.
        """
        # Prefer all_devices if available (multi-home support)
        if self._all_devices:
            return self._all_devices
        return self._devices

    def set_all_devices(self, devices: dict[str, dict]) -> None:
        """Set all devices across all homes.

        This is used for multi-home support to ensure all devices
        are accessible for child device parent lookups.

        Args:
            devices: Dictionary of all devices keyed by device ID
        """
        self._all_devices = devices.copy() if devices else {}
        _LOGGER.info(
            "Set all_devices cache with %s devices from all homes",
            len(self._all_devices),
        )

    @property
    def secure_id(self) -> str:
        """Get secure ID for MQTT."""
        return self._secure_id

    @property
    def secure_key(self) -> str:
        """Get secure key for MQTT."""
        return self._secure_key

    async def async_close(self) -> None:
        """Close client and cleanup resources."""
        if self._oauth_client:
            await self._oauth_client.deinit_async()
            self._oauth_client = None

        if self._http_client:
            await self._http_client.deinit_async()
            self._http_client = None

        self._access_token = None
        _LOGGER.info("Cloud client closed")
