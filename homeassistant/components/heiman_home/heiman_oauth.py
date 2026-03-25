"""OAuth2 Client for Heiman Cloud Integration.

This module implements OAuth2 Authorization Code Flow for Heiman Cloud authentication.
"""

import asyncio
import hashlib
import json
import logging
import secrets
import time
from urllib.parse import urlencode

import aiohttp

from .const import (
    OAUTH2_AUTH_URL,
    OAUTH2_CLIENT_SECRET,
    OAUTH2_TOKEN_URL,
    OAUTH2_USERINFO_URL,
)
from .heiman_error import HeimanError, HeimanErrorCode

_LOGGER = logging.getLogger(__name__)

# Token refresh margin (70% of expires_in)
TOKEN_EXPIRES_TS_RATIO = 0.7


def _raise_heiman_error(message: str, error_code: HeimanErrorCode) -> None:
    """Raise a Heiman error with the given message and code."""
    raise HeimanError(message, error_code)


class HeimanOauthClient:
    """OAuth2 client for Heiman Cloud authentication."""

    def __init__(
        self,
        client_id: str,
        redirect_url: str,
        cloud_server: str,
        region_config: dict,
        client_secret: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize OAuth2 client.

        Args:
            client_id: OAuth2 client ID
            redirect_url: OAuth2 redirect URI
            cloud_server: Cloud server region (cn, eu, test)
            region_config: Region configuration dict
            client_secret: OAuth2 client secret (optional)
            loop: Event loop
        """
        self._main_loop = loop or asyncio.get_running_loop()
        self._client_id = client_id
        self._client_secret = client_secret or OAUTH2_CLIENT_SECRET
        self._redirect_url = redirect_url
        self._cloud_server = cloud_server
        self._region_config = region_config

        # Generate unique state and device_id
        self._state = hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:32]
        self._device_id = f"ha.{self._state[:16]}"

        # OAuth2 endpoints from region config
        self._auth_url = region_config.get("oauth_auth_url", OAUTH2_AUTH_URL)
        self._token_url = region_config.get("oauth_token_url", OAUTH2_TOKEN_URL)
        self._userinfo_url = region_config.get(
            "oauth_userinfo_url",
            OAUTH2_USERINFO_URL,
        )

        # HTTP session
        self._session = aiohttp.ClientSession(loop=self._main_loop)

        _LOGGER.debug(">>> OAuth2 client initialized:")
        _LOGGER.debug(">>>   Cloud server: %s", self._cloud_server)
        _LOGGER.debug(">>>   Auth URL: %s", self._auth_url)
        _LOGGER.debug(">>>   Token URL: %s", self._token_url)
        _LOGGER.debug(">>>   UserInfo URL: %s", self._userinfo_url)
        _LOGGER.debug(">>>   Redirect URL: %s", self._redirect_url)
        _LOGGER.debug(">>>   Client ID: %s", self._client_id)
        _LOGGER.debug(
            ">>>   Client Secret: %s",
            self._client_secret[:8] + "***" if len(self._client_secret) > 8 else "***",
        )
        _LOGGER.debug(">>>   Device ID: %s", self._device_id)

    @property
    def state(self) -> str:
        """Return OAuth2 state parameter."""
        return self._state

    @property
    def device_id(self) -> str:
        """Return device ID for authentication."""
        return self._device_id

    async def deinit_async(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("OAuth2 client session closed")

    def set_redirect_url(self, redirect_url: str) -> None:
        """Update redirect URL.

        Args:
            redirect_url: New redirect URI

        Raises:
            HeimanError: If redirect_url is invalid
        """
        if not isinstance(redirect_url, str) or not redirect_url.strip():
            raise HeimanError(
                "invalid redirect_url",
                HeimanErrorCode.CODE_CONFIG_INVALID_INPUT,
            )
        self._redirect_url = redirect_url

    def gen_auth_url(
        self,
        redirect_url: str | None = None,
        state: str | None = None,
        scope: list | None = None,
        skip_confirm: bool | None = True,
    ) -> str:
        """Generate OAuth2 authorization URL.

        Args:
            redirect_url: Custom redirect URI (uses default if None)
            state: Custom state parameter (uses generated if None)
            scope: OAuth2 scope list
            skip_confirm: Skip confirmation screen for authorized users

        Returns:
            str: Complete authorization URL
        """
        params = {
            "redirect_uri": redirect_url or self._redirect_url,
            "client_id": self._client_id,
            "response_type": "code",
            "device_id": self._device_id,
            "state": state or self._state,
        }

        if scope:
            params["scope"] = " ".join(scope).strip()

        params["skip_confirm"] = "true" if skip_confirm else "false"
        encoded_params = urlencode(params)

        auth_url = f"{self._auth_url}?{encoded_params}"
        _LOGGER.debug("Generated auth URL: %s", auth_url)
        return auth_url

    async def __get_token_async(self, data: dict) -> dict:
        """Internal method to request token from OAuth2 server.

        Args:
          data: Request payload

        Returns:
            dict: Token response with expires_ts added

        Raises:
            HeimanError: If request fails or response is invalid
        """
        _LOGGER.debug(">>> OAuth Token Request - URL: %s", self._token_url)
        _LOGGER.debug(">>> OAuth Token Request - Data: %s", data)

        # Validate token URL before making request
        if not self._token_url or not self._token_url.startswith(
            ("http://", "https://"),
        ):
            _LOGGER.error("Invalid token URL: %s", self._token_url)
            raise HeimanError(
                f"invalid token url: {self._token_url}",
                HeimanErrorCode.CODE_CONFIG_INVALID_INPUT,
            )

        try:
            http_res = await self._session.post(
                url=self._token_url,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=aiohttp.ClientTimeout(total=60, connect=30),
            )

            res_str = await http_res.text()
            _LOGGER.debug("<<< OAuth Token Response - Status: %d", http_res.status)
            _LOGGER.debug("<<< OAuth Token Response - Body: %s", res_str)
            _LOGGER.debug(
                "<<< OAuth Token Response - Headers: %s",
                dict(http_res.headers),
            )

            if http_res.status == 401:
                _LOGGER.error("OAuth authentication failed (401 Unauthorized)")
                _LOGGER.error(
                    "grant_type: %s, client_id: %s",
                    data.get("grant_type"),
                    data.get("client_id"),
                )
                _raise_heiman_error(
                    "unauthorized(401)",
                    HeimanErrorCode.CODE_OAUTH_UNAUTHORIZED,
                )
            if http_res.status == 404:
                _LOGGER.error("OAuth token endpoint not found (404)")
                _LOGGER.error("Please check your region configuration and token URL")
                _raise_heiman_error(
                    f"token endpoint not found (404): {self._token_url}",
                    HeimanErrorCode.CODE_HTTP_ERROR,
                )
            if http_res.status != 200:
                _LOGGER.error("OAuth request failed with status: %d", http_res.status)
                _raise_heiman_error(
                    f"invalid http status code, {http_res.status}",
                    HeimanErrorCode.CODE_HTTP_ERROR,
                )

            res_obj = json.loads(res_str)

            # Validate response structure
            # Support both standard OAuth2 format and Heiman API format
            # Standard OAuth2: {"access_token": "...", "refresh_token": "...", "expires_in": ...}
            # Heiman API format: {"code": 0, "result": {"access_token": "...", ...}}
            if not res_obj:
                _LOGGER.error("Invalid token response: %s", res_str)
                _raise_heiman_error(
                    "invalid token response",
                    HeimanErrorCode.CODE_OAUTH_INVALID_RESPONSE,
                )

            # Check if it's standard OAuth2 format or Heiman API format
            if "result" in res_obj and res_obj.get("code", None) == 0:
                # Heiman API format
                token_data = res_obj["result"]
            elif "access_token" in res_obj:
                # Standard OAuth2 format
                token_data = res_obj
            else:
                _LOGGER.error("Invalid token response: %s", res_str)
                _raise_heiman_error(
                    "invalid token response",
                    HeimanErrorCode.CODE_OAUTH_INVALID_RESPONSE,
                )

            # Validate required fields
            if not all(
                key in token_data
                for key in ["access_token", "refresh_token", "expires_in"]
            ):
                _LOGGER.error("Invalid token response: %s", res_str)
                _raise_heiman_error(
                    "invalid token response",
                    HeimanErrorCode.CODE_OAUTH_INVALID_RESPONSE,
                )

            # Calculate token expiration timestamp (with 70% margin)
            expires_in = token_data.get("expires_in", 7200)
            expires_ts = int(time.time() + (expires_in * TOKEN_EXPIRES_TS_RATIO))

            result = {
                **token_data,
                "expires_ts": expires_ts,
            }

            _LOGGER.debug("Token obtained, expires at: %s", expires_ts)

        except json.JSONDecodeError as err:
            _LOGGER.error("JSON decode error: %s", err)
            raise HeimanError(
                f"json decode error: {err}",
                HeimanErrorCode.CODE_JSON_DECODE_ERROR,
            ) from err
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("HTTP connection error: %s", err)
            _LOGGER.error("Cannot connect to token server: %s", self._token_url)
            _LOGGER.error("Please check your network connection")
            raise HeimanError(
                f"connection error: {err}",
                HeimanErrorCode.CODE_HTTP_ERROR,
            ) from err
        except aiohttp.ServerTimeoutError as err:
            _LOGGER.error("HTTP timeout error: %s", err)
            _LOGGER.error("API request timeout")
            raise HeimanError(
                f"timeout error: {err}",
                HeimanErrorCode.CODE_HTTP_ERROR,
            ) from err
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP client error: %s", type(err).__name__)
            _LOGGER.error("Error details: %s", str(err))
            raise HeimanError(
                f"http client error: {type(err).__name__}: {err}",
                HeimanErrorCode.CODE_HTTP_ERROR,
            ) from err
        except Exception as err:
            _LOGGER.error(
                "Unexpected error during token exchange: %s",
                type(err).__name__,
            )
            _LOGGER.error("Error details: %s", str(err))
            raise HeimanError(
                f"unexpected error: {type(err).__name__}: {err}",
                HeimanErrorCode.CODE_OAUTH_INVALID_RESPONSE,
            ) from err
        else:
            return result

    async def get_access_token_async(self, code: str) -> dict:
        """Exchange authorization code for access token.

        Args:
            code: OAuth2 authorization code

        Returns:
            dict: Token response with access_token, refresh_token, expires_ts

        Raises:
            HeimanError: If code is invalid or request fails
        """
        _LOGGER.debug("=" * 80)
        _LOGGER.debug("Starting OAuth access token exchange")
        _LOGGER.debug("=" * 80)

        if not isinstance(code, str) or not code.strip():
            _LOGGER.error("Invalid authorization code: empty or not a string")
            raise HeimanError(
                "invalid authorization code",
                HeimanErrorCode.CODE_CONFIG_INVALID_INPUT,
            )

        _LOGGER.debug(">>> Authorization code (first 10 chars): %s...", code[:10])
        _LOGGER.debug(">>> Client ID: %s", self._client_id)
        _LOGGER.debug(
            ">>> Client Secret: %s",
            self._client_secret[:8] + "***" if len(self._client_secret) > 8 else "***",
        )
        _LOGGER.debug(">>> Redirect URI: %s", self._redirect_url)
        _LOGGER.debug(">>> Device ID: %s", self._device_id)

        token_data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_url,
            "code": code,
            "device_id": self._device_id,
        }

        try:
            result = await self.__get_token_async(token_data)
            _LOGGER.debug("=" * 80)
            _LOGGER.debug("OAuth access token exchange successful")
            _LOGGER.debug("=" * 80)
        except HeimanError:
            _LOGGER.error("=" * 80)
            _LOGGER.error("OAuth access token exchange failed")
            _LOGGER.error("=" * 80)
            raise
        else:
            return result

    async def refresh_access_token_async(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token

        Returns:
            dict: New token response

        Raises:
            HeimanError: If refresh_token is invalid or request fails
        """
        _LOGGER.debug("=" * 80)
        _LOGGER.debug("Starting OAuth token refresh")
        _LOGGER.debug("=" * 80)

        if not isinstance(refresh_token, str) or not refresh_token.strip():
            _LOGGER.error("Invalid refresh token: empty or not a string")
            raise HeimanError(
                "invalid refresh token",
                HeimanErrorCode.CODE_CONFIG_INVALID_INPUT,
            )

        _LOGGER.debug(">>> Refresh token (first 10 chars): %s...", refresh_token[:10])
        _LOGGER.debug(">>> Client ID: %s", self._client_id)
        _LOGGER.debug(
            ">>> Client Secret: %s",
            self._client_secret[:8] + "***" if len(self._client_secret) > 8 else "***",
        )
        _LOGGER.debug(">>> Redirect URI: %s", self._redirect_url)

        token_data = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_url,
            "refresh_token": refresh_token,
        }

        try:
            result = await self.__get_token_async(token_data)
            _LOGGER.debug("=" * 80)
            _LOGGER.debug("OAuth token refresh successful")
            _LOGGER.debug("=" * 80)
        except HeimanError:
            _LOGGER.error("=" * 80)
            _LOGGER.error("OAuth token refresh failed")
            _LOGGER.error("=" * 80)
            raise
        else:
            return result


class HeimanHttpClient:
    """HTTP client for Heiman Cloud API."""

    def __init__(
        self,
        api_url: str,
        client_id: str,
        access_token: str,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize HTTP client.

        Args:
            api_url: Base API URL
            client_id: Client ID for requests
            access_token: OAuth2 access token
            loop: Event loop
        """
        self._main_loop = loop or asyncio.get_running_loop()
        self._api_url = api_url
        self._client_id = client_id
        self._access_token = access_token
        self._session = aiohttp.ClientSession(loop=self._main_loop)

        _LOGGER.debug(">>> HTTP client initialized:")
        _LOGGER.debug(">>>   API URL: %s", api_url)
        _LOGGER.debug(">>>   Client ID: %s", client_id)
        _LOGGER.debug(">>>   Access token (first 20 chars): %s...", access_token[:20])

    async def deinit_async(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("HTTP client session closed")

    def update_http_header(
        self,
        access_token: str | None = None,
    ) -> None:
        """Update HTTP headers.

        Args:
            access_token: New access token
        """
        if isinstance(access_token, str):
            self._access_token = access_token

    @property
    def _api_request_headers(self) -> dict:
        """Generate API request headers."""
        return {
            "Authorization": f"bearer {self._access_token}",
            "Content-Type": "application/json",
            # "X-Client-Id": self._client_id,
        }

    async def _api_get_async(
        self,
        path: str,
        params: dict | None = None,
        timeout: int = 30,
    ) -> dict:
        """Make GET request to API.

        Args:
            path: API path (relative to base URL)
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            dict: API response

        Raises:
            HeimanError: If request fails
        """
        url = f"{self._api_url}{path}"
        _LOGGER.debug(">>> API GET Request - URL: %s", url)
        _LOGGER.debug(">>> API GET Request - Params: %s", params)

        try:
            http_res = await self._session.get(
                url=url,
                params=params,
                headers=self._api_request_headers,
                timeout=aiohttp.ClientTimeout(total=60, connect=30),
            )

            res_str = await http_res.text()
            _LOGGER.debug("<<< API GET Response - Status: %d", http_res.status)
            _LOGGER.debug("<<< API GET Response - Body: %s", res_str)

            if http_res.status == 401:
                _raise_heiman_error(
                    "unauthorized(401)",
                    HeimanErrorCode.CODE_HTTP_UNAUTHORIZED,
                )
            if http_res.status != 200:
                _raise_heiman_error(
                    f"invalid http status code, {http_res.status}",
                    HeimanErrorCode.CODE_HTTP_ERROR,
                )

            res_obj = json.loads(res_str)

            # Heiman API response can be in two formats:
            # Format 1: {"code": 0, "result": {...}, "msg": "..."}
            # Format 2: {"status": 200, "result": {...}, "message": "..."}
            # Support both formats for backward compatibility

            api_status = res_obj.get("status", None)

            # Check for success in either format
            is_success = api_status == 200

            if not is_success:
                # Try to get error message from either format
                error_msg = (
                    res_obj.get("msg") or res_obj.get("message") or "unknown error"
                )
                _LOGGER.error(
                    "API error: %s, path: %s, params: %s",
                    error_msg,
                    path,
                    params,
                )
                _LOGGER.error(
                    "API response - status: %s, msg: %s, message: %s",
                    api_status,
                    res_obj.get("msg"),
                    res_obj.get("message"),
                )
                _raise_heiman_error(
                    f"api error: {error_msg}",
                    HeimanErrorCode.CODE_API_ERROR,
                )

            _LOGGER.debug("API GET success: %s", path)
            return res_obj.get("result", {})

        except json.JSONDecodeError as err:
            _LOGGER.error("JSON decode error: %s", err)
            raise HeimanError(
                f"json decode error: {err}",
                HeimanErrorCode.CODE_JSON_DECODE_ERROR,
            ) from err
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("HTTP connection error: %s", err)
            _LOGGER.error("Cannot connect to token server: %s", self._token_url)
            _LOGGER.error("Please check your network connection")
            raise HeimanError(
                f"connection error: {err}",
                HeimanErrorCode.CODE_HTTP_ERROR,
            ) from err
        except aiohttp.ServerTimeoutError as err:
            _LOGGER.error("HTTP timeout error: %s", err)
            _LOGGER.error("API request timeout")
            raise HeimanError(
                f"timeout error: {err}",
                HeimanErrorCode.CODE_HTTP_ERROR,
            ) from err
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP client error: %s", type(err).__name__)
            _LOGGER.error("Error details: %s", str(err))
            raise HeimanError(
                f"http client error: {type(err).__name__}: {err}",
                HeimanErrorCode.CODE_HTTP_ERROR,
            ) from err
        except Exception as err:
            _LOGGER.error(
                "Unexpected error during token exchange: %s",
                type(err).__name__,
            )
            _LOGGER.error("Error details: %s", str(err))
            raise HeimanError(
                f"unexpected error: {type(err).__name__}: {err}",
                HeimanErrorCode.CODE_OAUTH_INVALID_RESPONSE,
            ) from err

    async def api_get_async(
        self,
        path: str,
        params: dict | None = None,
        timeout: int = 30,
    ) -> dict:
        """Make a public GET request to the API."""
        return await self._api_get_async(path=path, params=params, timeout=timeout)

    async def _api_post_async(
        self,
        path: str,
        data: dict | list,
        timeout: int = 30,
    ) -> dict | list:
        """Make POST request to API.

        Args:
            path: API path (relative to base URL)
            data: Request body (dict or list)
            timeout: Request timeout in seconds

        Returns:
            dict or list: API response

        Raises:
            HeimanError: If request fails
        """
        url = f"{self._api_url}{path}"
        _LOGGER.debug(">>> API POST Request - URL: %s", url)
        _LOGGER.debug(">>> API POST Request - Data: %s", data)

        try:
            http_res = await self._session.post(
                url=url,
                json=data,
                headers=self._api_request_headers,
                timeout=aiohttp.ClientTimeout(total=60, connect=30),
            )

            res_str = await http_res.text()
            _LOGGER.debug("<<< API POST Response - Status: %d", http_res.status)
            _LOGGER.debug("<<< API POST Response - Body: %s", res_str)

            if http_res.status == 401:
                _raise_heiman_error(
                    "unauthorized(401)",
                    HeimanErrorCode.CODE_HTTP_UNAUTHORIZED,
                )
            if http_res.status != 200:
                _raise_heiman_error(
                    f"invalid http status code, {http_res.status}",
                    HeimanErrorCode.CODE_HTTP_ERROR,
                )

            res_obj = json.loads(res_str)

            # Heiman API response can be in two formats:
            # Format 1: {"code": 0, "result": {...}, "msg": "..."}
            # Format 2: {"status": 200, "result": {...}, "message": "..."}
            # Support both formats for backward compatibility
            api_code = res_obj.get("code", None)
            api_status = res_obj.get("status", None)

            # Check for success in either format
            is_success = (api_code == 0) or (api_status == 200)

            if not is_success:
                # Try to get error message from either format
                error_msg = (
                    res_obj.get("msg") or res_obj.get("message") or "unknown error"
                )
                _LOGGER.error(
                    "API error: %s, path: %s, data: %s",
                    error_msg,
                    path,
                    data,
                )
                _LOGGER.error(
                    "API response - code: %s, status: %s, msg: %s, message: %s",
                    api_code,
                    api_status,
                    res_obj.get("msg"),
                    res_obj.get("message"),
                )
                _raise_heiman_error(
                    f"api error: {error_msg}",
                    HeimanErrorCode.CODE_API_ERROR,
                )

            _LOGGER.debug("API POST success: %s", path)
            return res_obj.get("result", {})

        except json.JSONDecodeError as err:
            _LOGGER.error("JSON decode error: %s", err)
            raise HeimanError(
                f"json decode error: {err}",
                HeimanErrorCode.CODE_JSON_DECODE_ERROR,
            ) from err
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("HTTP connection error: %s", err)
            _LOGGER.error("Cannot connect to token server: %s", self._token_url)
            _LOGGER.error("Please check your network connection")
            raise HeimanError(
                f"connection error: {err}",
                HeimanErrorCode.CODE_HTTP_ERROR,
            ) from err
        except aiohttp.ServerTimeoutError as err:
            _LOGGER.error("HTTP timeout error: %s", err)
            _LOGGER.error("API request timeout")
            raise HeimanError(
                f"timeout error: {err}",
                HeimanErrorCode.CODE_HTTP_ERROR,
            ) from err
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP client error: %s", type(err).__name__)
            _LOGGER.error("Error details: %s", str(err))
            raise HeimanError(
                f"http client error: {type(err).__name__}: {err}",
                HeimanErrorCode.CODE_HTTP_ERROR,
            ) from err
        except Exception as err:
            _LOGGER.error(
                "Unexpected error during token exchange: %s",
                type(err).__name__,
            )
            _LOGGER.error("Error details: %s", str(err))
            raise HeimanError(
                f"unexpected error: {type(err).__name__}: {err}",
                HeimanErrorCode.CODE_OAUTH_INVALID_RESPONSE,
            ) from err

    async def api_post_async(
        self,
        path: str,
        data: dict | list,
        timeout: int = 30,
    ) -> dict | list:
        """Make a public POST request to the API."""
        return await self._api_post_async(path=path, data=data, timeout=timeout)

    async def get_user_info_async(self) -> dict:
        """Get current user information.

        Returns:
            dict: User info including userId, email, etc.

        Raises:
            HeimanError: If request fails
        """
        _LOGGER.debug("Getting user info")
        return await self._api_get_async("/api-app/appUser/get/info", params={})

    async def get_homes_async(self, user_id: str) -> dict:
        """Get user's home list.

        Args:
            user_id: User ID for requesting home list

        Returns:
            dict: Home list

        Raises:
            HeimanError: If request fails
        """
        _LOGGER.debug("Getting homes list for user: %s", user_id)
        return await self._api_post_async(
            "/api-app/homeUserRelation/get/homeList",
            data={"userId": user_id},
        )

    async def get_devices_async(
        self,
        home_id: str,
        user_id: str,
        secure_id: str,
    ) -> dict:
        """Get devices in a home.

        Args:
            home_id: Home ID
            user_id: User ID
            secure_id: Secure ID

        Returns:
            dict: Device list

        Raises:
            HeimanError: If request fails
        """
        _LOGGER.debug("Getting devices for home: %s", home_id)

        # Use pagination API to get devices
        request_data = {
            "help": {"pageSize": 100, "pageNumber": 1},
            "custom": {
                "homeId": home_id,
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
                "secureId": secure_id,
                "userId": user_id,
            },
        }

        return await self._api_post_async(
            "/api-app/device/get/listByPage",
            data=request_data,
        )

    async def get_device_info_async(self, device_id: str) -> dict:
        """Get device details.

        Args:
            device_id: Device ID

        Returns:
            dict: Device information

        Raises:
            HeimanError: If request fails
        """
        _LOGGER.debug("Getting device info: %s", device_id)
        return await self._api_post_async(
            "/api-app/device/get/info",
            data={"deviceId": device_id},
        )
