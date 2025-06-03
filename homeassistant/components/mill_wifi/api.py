import httpx
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from .const import (
    BASE_URL,
    ENDPOINT_AUTH_SIGN_IN,
    ENDPOINT_AUTH_REFRESH,
    ENDPOINT_CUSTOMER_SETTINGS,
    ENDPOINT_HOUSE_DEVICES_FORMAT,
    ENDPOINT_HOUSE_INDEPENDENT_DEVICES_FORMAT,
    ENDPOINT_DEVICE_DATA_FORMAT,
    ENDPOINT_DEVICE_SETTINGS_FORMAT,
    TOKEN_REFRESH_OFFSET,
)
from .device_metric import DeviceMetric
from .device_capability import (
    EDeviceCapability, 
    EDeviceType,
    EOperationMode, 
    EPredictiveHeatingType, 
    ELockMode, 
    EAdditionalSocketMode, 
    ERegulatorType,
    EPurifierFanMode, 
)

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "homeassistant-mill-official/0.1.0" 
MAX_REQUEST_RETRIES = 3
INITIAL_BACKOFF_FACTOR = 5
MAX_BACKOFF_DELAY = 120

class AuthenticationError(Exception):
    """Custom exception for authentication failures."""
    pass

class MillApiError(Exception):
    """Custom exception for general API errors after retries."""
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code

class MillApiClient:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.token_expires_at: datetime | None = None
        self.client: httpx.AsyncClient | None = None
        self._auth_lock = asyncio.Lock()
        self._client_lock = asyncio.Lock()
        self._is_refreshing_token = False 

    async def _ensure_client(self):
        async with self._client_lock:
            if self.client is None or self.client.is_closed:
                _LOGGER.debug("Initializing httpx.AsyncClient with User-Agent: %s", USER_AGENT)
                headers = {"User-Agent": USER_AGENT}
                timeout_config = httpx.Timeout(20.0, connect=30.0) 
                self.client = httpx.AsyncClient(timeout=timeout_config, headers=headers)

    async def async_setup(self):
        await self._ensure_client()

    async def async_close(self):
        async with self._client_lock:
            if self.client and not self.client.is_closed:
                await self.client.aclose()
                self.client = None

    async def _raw_request(self, method: str, url: str, headers: dict | None = None, attempt: int = 1, **kwargs: Any) -> httpx.Response:
        await self._ensure_client()
        if self.client is None:
            _LOGGER.critical("HTTP client is None before making a raw request for %s.", url)
            raise ConnectionError("HTTP client not initialized")

        final_headers = {**self.client.headers, **(headers or {})}
        full_url = f"{BASE_URL}{url}"

        log_body = kwargs.get('json')
        if url == ENDPOINT_AUTH_SIGN_IN and isinstance(log_body, dict):
            log_body = {k: ("********" if k == "password" else v) for k,v in log_body.items()}

        _LOGGER.debug("Raw Request (Attempt %d): %s %s, Headers: %s, Body: %s", attempt, method, full_url, final_headers, log_body)
        
        try:
            response = await self.client.request(method, full_url, headers=final_headers, **kwargs)
            _LOGGER.debug("Raw Response for %s (Attempt %d): %s, Body: %s", full_url, attempt, response.status_code, response.text[:500] if response.text else "No Content")
            
            if response.status_code == 429: 
                if attempt < MAX_REQUEST_RETRIES:
                    retry_after_header = response.headers.get("Retry-After")
                    try:
                        retry_after = int(retry_after_header) if retry_after_header else (INITIAL_BACKOFF_FACTOR * attempt)
                        retry_after = min(retry_after, MAX_BACKOFF_DELAY)
                    except ValueError:
                        retry_after = min(INITIAL_BACKOFF_FACTOR * attempt, MAX_BACKOFF_DELAY)

                    _LOGGER.warning("Rate limit (429) for %s. Retrying in %d seconds (attempt %d/%d)...", full_url, retry_after, attempt, MAX_REQUEST_RETRIES)
                    await asyncio.sleep(retry_after)
                    return await self._raw_request(method, url, headers=headers, attempt=attempt + 1, **kwargs)
                else:
                    _LOGGER.error("Rate limit (429) for %s. Max retries (%d) exceeded.", full_url, MAX_REQUEST_RETRIES)
                    raise MillApiError(f"Rate limit exceeded for {full_url}", status_code=response.status_code)
            
            response.raise_for_status() 
            return response
        except httpx.HTTPStatusError as e:
            _LOGGER.error("Raw HTTP error %s calling %s after %d attempts: %s", e.response.status_code, e.request.url, attempt, e.response.text[:500])
            raise MillApiError(f"API returned {e.response.status_code} for {e.request.url}", status_code=e.response.status_code) from e
        except httpx.RequestError as e: 
            _LOGGER.error("Raw Request error calling %s after %d attempts: %s", e.request.url if e.request else "unknown URL", attempt, e)
            if attempt < MAX_REQUEST_RETRIES:
                retry_after = min(INITIAL_BACKOFF_FACTOR * attempt, MAX_BACKOFF_DELAY)
                _LOGGER.warning("Request error for %s. Retrying in %d seconds (attempt %d/%d)...", full_url, retry_after, attempt, MAX_REQUEST_RETRIES)
                await asyncio.sleep(retry_after)
                return await self._raw_request(method, url, headers=headers, attempt=attempt + 1, **kwargs)
            _LOGGER.error("Request error for %s. Max retries (%d) exceeded.", full_url, MAX_REQUEST_RETRIES)
            raise MillApiError(f"Request failed for {e.request.url if e.request else 'unknown URL'} after multiple retries") from e


    async def _ensure_valid_token(self, force_refresh: bool = False):
        async with self._auth_lock: 
            if self._is_refreshing_token and not force_refresh: 
                _LOGGER.debug("Token refresh already in progress, waiting for it to complete.")
                while self._is_refreshing_token: 
                    await asyncio.sleep(0.5)
                if self.access_token and self.token_expires_at and \
                    self.token_expires_at > datetime.now(timezone.utc) + timedelta(seconds=TOKEN_REFRESH_OFFSET):
                        return 

            if not force_refresh and self.access_token and self.token_expires_at and \
                self.token_expires_at > datetime.now(timezone.utc) + timedelta(seconds=TOKEN_REFRESH_OFFSET):
                    _LOGGER.debug("Token is still valid until %s.", self.token_expires_at)
                    return

            self._is_refreshing_token = True
            try:
                _LOGGER.info("Token is expired or nearing expiry (Force refresh: %s). Attempting renewal.", force_refresh)
                
                if self.refresh_token and not force_refresh: 
                    try:
                        _LOGGER.info("Attempting token refresh with refresh_token.")
                        await self.async_refresh_token_internal()
                        if self.access_token:
                            _LOGGER.info("Token refresh successful via refresh_token path.")
                            self._is_refreshing_token = False
                            return
                    except AuthenticationError as auth_err:
                        _LOGGER.warning("Refreshing token with refresh_token failed (auth error): %s. Invalidating tokens and will attempt full login.", auth_err)
                        self._clear_tokens()
                    except MillApiError as api_err: 
                        _LOGGER.warning("Refreshing token with refresh_token failed (API error %s): %s. Invalidating tokens.", api_err.status_code, api_err)
                        self._clear_tokens()
                    except Exception as e: 
                        _LOGGER.exception("Unexpected error during token refresh: %s. Invalidating tokens.", e)
                        self._clear_tokens()
                else:
                    _LOGGER.info("No valid refresh token or force_refresh is True, proceeding to full login.")

                _LOGGER.info("Attempting full login as part of token renewal process.")
                await self.login_internal() 
                if self.access_token:
                    _LOGGER.info("Full login successful during token renewal.")
                else: 
                    _LOGGER.critical("Full login completed but access_token is STILL NOT SET.")
                    raise AuthenticationError("Full login did not result in a valid access token.")
            finally:
                self._is_refreshing_token = False


    def _clear_tokens(self):
        self.access_token = None
        self.refresh_token = None 
        self.token_expires_at = None


    async def _request(self, method: str, url: str, retry_on_auth_error: bool = True, **kwargs: Any) -> httpx.Response:
        await self._ensure_client()
        if self.client is None:
            _LOGGER.critical("HTTP client is None for _request to %s.", url)
            raise ConnectionError("HTTP client not initialized for _request")

        await self._ensure_valid_token() 
        
        if not self.access_token:
            _LOGGER.error("No access token available after _ensure_valid_token for %s.", url)
            raise AuthenticationError("Access token unavailable after validation.")

        request_headers = kwargs.pop("headers", {}) 
        request_headers["Authorization"] = f"Bearer {self.access_token}"
        
        try:
            return await self._raw_request(method, url, headers=request_headers, **kwargs)
        except MillApiError as e:
            if e.status_code == 401 and retry_on_auth_error:
                _LOGGER.warning("Received 401 for %s. Attempting token refresh and retrying request once.", url)
                await self._ensure_valid_token(force_refresh=True) 
                
                if not self.access_token: 
                    _LOGGER.error("Failed to obtain a new token after 401. Giving up on request to %s.", url)
                    raise AuthenticationError("Failed to re-authenticate after 401.") from e

                request_headers["Authorization"] = f"Bearer {self.access_token}"
                _LOGGER.info("Retrying request to %s with new token.", url)
                return await self._raw_request(method, url, headers=request_headers, **kwargs) 
            raise 

    async def login_internal(self):
        _LOGGER.debug("Executing login_internal.")
        try:
            response = await self._raw_request(
                "POST", ENDPOINT_AUTH_SIGN_IN,
                json={"login": self.username, "password": self.password}
            )
            data = response.json()
            self.access_token = data.get("idToken")
            self.refresh_token = data.get("refreshToken") 
            if not self.access_token or not self.refresh_token:
                _LOGGER.error("Login response missing tokens: %s", data)
                self._clear_tokens()
                raise AuthenticationError("Login response did not contain required tokens.")
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=59) 
            _LOGGER.info("login_internal successful. New token expires at %s", self.token_expires_at)
        except (MillApiError, AuthenticationError) as e:
            _LOGGER.error("login_internal failed: %s", e)
            self._clear_tokens()
            raise
        except Exception as e: 
            _LOGGER.exception("Unexpected error in login_internal: %s", e)
            self._clear_tokens()
            raise AuthenticationError(f"Unexpected login failure: {e}") from e


    async def async_refresh_token_internal(self):
        if not self.refresh_token:
            _LOGGER.error("Cannot refresh: No refresh token available.")
            raise AuthenticationError("No refresh token to refresh with")

        _LOGGER.debug("Executing async_refresh_token_internal.")
        current_refresh_token = self.refresh_token
        try:
            headers = {"Authorization": f"Bearer {current_refresh_token}"}
            response = await self._raw_request("POST", ENDPOINT_AUTH_REFRESH, headers=headers)
            data = response.json()
            
            new_id_token = data.get("idToken")
            new_refresh_token = data.get("refreshToken")

            if not new_id_token: 
                _LOGGER.error("Token refresh response missing idToken. Data: %s. Refresh token used: %s", data, current_refresh_token)
                self.access_token = None
                self.token_expires_at = None
                raise AuthenticationError("Token refresh response did not contain idToken.")

            self.access_token = new_id_token
            if new_refresh_token: 
                self.refresh_token = new_refresh_token
            
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=59)
            _LOGGER.info("async_refresh_token_internal successful. New access token expires at %s", self.token_expires_at)
        
        except MillApiError as e:
            _LOGGER.error("async_refresh_token_internal failed with MillApiError (status %s): %s. Refresh token used: %s", e.status_code, e, current_refresh_token)
            if e.status_code == 401:
                self._clear_tokens()
            else: 
                self.access_token = None
                self.token_expires_at = None
            raise AuthenticationError(f"Token refresh API error: {e}") from e
        except AuthenticationError: 
            raise
        except Exception as e: 
            _LOGGER.exception("Unexpected error in async_refresh_token_internal (refresh token used: %s): %s", current_refresh_token, e)
            self.access_token = None 
            self.token_expires_at = None
            raise AuthenticationError(f"Unexpected token refresh failure: {e}") from e


    async def login(self): 
        async with self._auth_lock:
            self._is_refreshing_token = True 
            try:
                await self.login_internal()
                if not self.access_token: 
                    _LOGGER.critical("Public login call completed but access_token not set.")
                    raise AuthenticationError("Initial login failed to acquire token.")
            finally:
                self._is_refreshing_token = False
    
    async def _patch_device_settings(self, device_id: str, payload: dict):
        return await self._request( 
            "PATCH",
            ENDPOINT_DEVICE_SETTINGS_FORMAT.format(device_id=device_id),
            json=payload,
        )

    async def get_all_devices(self):
        _LOGGER.debug("Attempting to get all devices.")
        response = await self._request("GET", ENDPOINT_CUSTOMER_SETTINGS, retry_on_auth_error=True)
        
        customer_data = response.json()
        houses = customer_data.get("houseList", [])
        devices = []
        if not houses:
            _LOGGER.warning("No houses found in API response for get_all_devices.")
            return []

        for house in houses:
            house_id = house.get("houseId")
            if not house_id:
                _LOGGER.warning("House entry missing houseId: %s", house)
                continue
            
            for path_template in [ENDPOINT_HOUSE_DEVICES_FORMAT, ENDPOINT_HOUSE_INDEPENDENT_DEVICES_FORMAT]:
                path = path_template.format(house_id=house_id)
                try:
                    r = await self._request("GET", path, retry_on_auth_error=True)
                    data = r.json()
                    
                    if isinstance(data, dict) and "items" in data: 
                        devices.extend(data.get("items", []))
                    elif isinstance(data, list): 
                        for room_or_device in data:
                            if "devices" in room_or_device: 
                                devices.extend(room_or_device.get("devices", []))
                            elif "deviceId" in room_or_device: 
                                devices.append(room_or_device)
                    else:
                        _LOGGER.warning("Unexpected data format from %s for house %s: %s", path, house_id, str(data)[:200])

                except AuthenticationError:
                    _LOGGER.error("Authentication error while fetching devices from %s for house %s. Re-raising.", path, house_id)
                    raise 
                except MillApiError as e:
                    _LOGGER.error("Mill API error fetching devices from path %s for house %s (status %s): %s", path, house_id, e.status_code, e)
                except Exception as e:
                    _LOGGER.exception("Unexpected error fetching devices from path %s for house %s: %s", path, house_id, e)
        
        _LOGGER.info("Found %d devices in total after processing all houses.", len(devices))
        return devices
        
    async def get_device_data(self, device_id: str):
        try:
            response = await self._request("GET", ENDPOINT_DEVICE_DATA_FORMAT.format(device_id=device_id), retry_on_auth_error=True)
            return response.json()
        except MillApiError as e:
            _LOGGER.error("Fetching device %s failed in get_device_data (status %s): %s", device_id, e.status_code, e)
            if e.status_code == 404:
                return None 
            raise 
        except AuthenticationError:
            _LOGGER.error("Authentication error while fetching device data for %s. Re-raising.", device_id)
            raise
        except Exception as e:
            _LOGGER.exception("Unexpected error fetching device %s in get_device_data: %s", device_id, e)
            return None 

    async def _get_parent_type(self, device_data: dict, device_id: str, operation: str) -> str:
        parent_type = device_data.get("deviceType", {}).get("parentType", {}).get("name")
        if not parent_type:
            device_type_name = DeviceMetric.get_device_type(device_data) or "Unknown Type"
            _LOGGER.warning(
                "Parent type not found for device %s (%s) during %s. Attempting to infer.",
                device_id, device_type_name, operation
            )
            if device_type_name: 
                if "Socket" in device_type_name: parent_type = "Sockets"
                elif "Panel Heater" in device_type_name or "Convection" in device_type_name or "Oil Heater" in device_type_name : parent_type = "Heaters"
                elif "Sense" in device_type_name: parent_type = "Sensors" 
                elif "Air Purifier" in device_type_name: parent_type = "Air Purifiers"
                elif "Heat Pump" in device_type_name: parent_type = "Heat Pumps" 
                else:
                    _LOGGER.error("Could not infer parent type for %s (%s). This may cause API errors.", device_id, device_type_name)
                    raise ValueError(f"Cannot determine parentType for device {device_id} ({device_type_name})")
            else:
                _LOGGER.error("Device type name also missing for %s. Cannot determine parentType.", device_id)
                raise ValueError(f"Cannot determine parentType for device {device_id} (no childType name)")
        return parent_type

    async def set_device_power(self, device_id: str, enabled: bool, device_data: dict):
        parent_type = await self._get_parent_type(device_data, device_id, "set_device_power")
        payload = {
            "deviceType": parent_type,
            "enabled": bool(enabled), 
            "settings": {} 
        }
        _LOGGER.debug("Setting device power for %s with payload: %s", device_id, payload)
        await self._patch_device_settings(device_id, payload)


    async def set_switch_capability(self, device_id: str, capability_str: str, value: bool, device_data: dict):
        settings = {}
        key_map = {
            EDeviceCapability.INDIVIDUAL_CONTROL: ("operation_mode", EOperationMode.CONTROL_INDIVIDUALLY.value, EOperationMode.WEEKLY_PROGRAM.value),
            EDeviceCapability.PREDICTIVE_HEATING: ("predictive_heating_type", EPredictiveHeatingType.ADVANCED.value, EPredictiveHeatingType.OFF.value),
            EDeviceCapability.CHILD_LOCK: ("lock_status", ELockMode.CHILD.value, ELockMode.NO_LOCK.value),
            EDeviceCapability.COMMERCIAL_LOCK: ("lock_status", ELockMode.COMMERCIAL.value, ELockMode.NO_LOCK.value), 
            EDeviceCapability.OPEN_WINDOW: ("open_window", {"enabled": True}, {"enabled": False}), 
            EDeviceCapability.COOLING_MODE: ("additional_socket_mode", EAdditionalSocketMode.COOLING.value, None), 
            EDeviceCapability.PID_CONTROLLER: ("regulator_type", ERegulatorType.PID.value, ERegulatorType.HYSTERESIS_OR_SLOW_PID.value), 
            EDeviceCapability.SLOW_PID: ("regulator_type", ERegulatorType.HYSTERESIS_OR_SLOW_PID.value, ERegulatorType.PID.value), 
            EDeviceCapability.GREE_DISPLAY_LIGHT: ("display_light", "on", "off"), 
        }

        if capability_str == EDeviceCapability.ONOFF.value: 
            return await self.set_device_power(device_id, value, device_data)

        key_info = key_map.get(EDeviceCapability(capability_str))
        if key_info is None:
            _LOGGER.error(f"Unsupported switch capability string: {capability_str} in key_map")
            raise ValueError(f"Unsupported switch capability string: {capability_str}")

        field, val_on, val_off = key_info
        
        if capability_str == EDeviceCapability.COOLING_MODE.value and not value: 
            settings[field] = None 
        elif capability_str == EDeviceCapability.OPEN_WINDOW.value: 
            settings[field] = val_on if value else val_off
        else:
            settings[field] = val_on if value else val_off
        
        parent_type = await self._get_parent_type(device_data, device_id, f"set_switch_capability: {capability_str}")
        current_power_state = DeviceMetric.get_power_state(device_data)

        payload = {
            "deviceType": parent_type,
            "enabled": current_power_state, 
            "settings": settings
        }
        _LOGGER.debug("Setting switch capability %s for %s with payload: %s", capability_str, device_id, payload)
        await self._patch_device_settings(device_id, payload)

    async def set_number_capability(self, device_id: str, capability_str: str, value: float, device_data: dict):
        settings = {}
        if capability_str == EDeviceCapability.TARGET_TEMPERATURE.value:
            settings["temperature_normal"] = float(value)
        elif capability_str == EDeviceCapability.ADJUST_WATTAGE.value: 
            settings["limited_heating_power"] = int(round(value)) 
        else:
            raise ValueError(f"Unsupported number capability: {capability_str}")

        parent_type = await self._get_parent_type(device_data, device_id, f"set_number_capability: {capability_str}")
        current_power_state = DeviceMetric.get_power_state(device_data)

        payload = {
            "deviceType": parent_type,
            "enabled": current_power_state, 
            "settings": settings
        }
        _LOGGER.debug("Setting number capability %s for %s with payload: %s", capability_str, device_id, payload)
        await self._patch_device_settings(device_id, payload)

    async def set_select_capability(self, device_id: str, capability_str: str, value: str, device_data: dict):
        parent_type = await self._get_parent_type(device_data, device_id, f"set_select_capability: {capability_str}")
        payload = {}

        if EDeviceCapability(capability_str) == EDeviceCapability.PURIFIER_MODE:
            is_target_mode_an_off_state = value == EPurifierFanMode.SOFT_OFF.value 

            payload_enabled_state = not is_target_mode_an_off_state

            payload = {
                "deviceType": parent_type, 
                "enabled": payload_enabled_state,
                "settings": { 
                    "fan_speed_mode": value 
                }
            }
            _LOGGER.info(
                "Setting purifier mode for %s. Target mode: %s, Payload 'enabled': %s, Full payload: %s",
                device_id, value, payload_enabled_state, payload
            )
        else:
            _LOGGER.error(f"Unsupported select capability for API call: {capability_str}")
            raise ValueError(f"Unsupported select capability: {capability_str}")
            
        _LOGGER.debug("Setting select capability %s for %s with payload: %s", capability_str, device_id, payload)
        await self._patch_device_settings(device_id, payload)
