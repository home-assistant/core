"""API client for Eufy Security.

Uses the v2 API with ECDH encryption, based on eufy-security-client by bropat.
"""

from __future__ import annotations

from datetime import datetime
import json as json_module
import logging
import time
from typing import Any

from aiohttp import ClientError, ClientSession
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

from .crypto import decrypt_api_data, encrypt_api_data
from .exceptions import (
    CannotConnectError,
    CaptchaRequiredError,
    EufySecurityError,
    InvalidCredentialsError,
    RequestError,
    raise_on_error,
)
from .models import Camera, Station

_LOGGER = logging.getLogger(__name__)

# API endpoints
DOMAIN_LOOKUP_URL = "https://extend.eufylife.com/domain"

# Server public key for ECDH key exchange (from eufy-security-client)
# Used only for initial login encryption
SERVER_PUBLIC_KEY = bytes.fromhex(
    "04c5c00c4f8d1197cc7c3167c52bf7acb054d722f0ef08dcd7e0883236e0d72a"
    "3868d9750cb47fa4619248f3d83f0f662671dadc6e2d31c2f41db0161651c7c076"
)

# Default headers that mimic the Android app
DEFAULT_HEADERS = {
    "App_version": "v4.6.0_1630",
    "Os_type": "android",
    "Os_version": "31",
    "Phone_model": "ONEPLUS A3003",
    "Language": "en",
    "Openudid": "5e4621b0152c0d00",
    "Net_type": "wifi",
    "Mnc": "02",
    "Mcc": "310",
    "Sn": "75814221ee75",
    "Model_type": "PHONE",
    "Timezone": "GMT-08:00",
    "Cache-Control": "no-cache",
}


class EufySecurityAPI:
    """API client for Eufy Security using v2 encrypted API."""

    def __init__(
        self, session: ClientSession, email: str, password: str, country: str = "US"
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._email = email
        self._password = password
        self._country = country
        self._api_base: str | None = None
        self._token: str | None = None
        self._token_expiration: datetime | None = None
        self._retry_on_401 = False
        self.cameras: dict[str, Camera] = {}
        self.stations: dict[str, Station] = {}

        # Generate ECDH key pair for encrypted communication
        self._private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        self._public_key = self._private_key.public_key()
        self._client_public_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )

        # Compute shared secret with hardcoded server key (for login only)
        server_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), SERVER_PUBLIC_KEY
        )
        self._login_shared_secret = self._private_key.exchange(
            ec.ECDH(), server_public_key
        )

        # This will be set after login with the server's returned public key
        self._response_shared_secret: bytes | None = None
        # Store server public key hex for serialization
        self._server_public_key_hex: str | None = None

    @property
    def token(self) -> str | None:
        """Return the current auth token."""
        return self._token

    @property
    def token_expiration(self) -> datetime | None:
        """Return the token expiration datetime."""
        return self._token_expiration

    @property
    def api_base(self) -> str | None:
        """Return the API base URL."""
        return self._api_base

    def set_token(
        self,
        token: str,
        expiration: datetime | None = None,
        api_base: str | None = None,
    ) -> None:
        """Set the auth token directly (for restoring from stored config)."""
        self._token = token
        self._token_expiration = expiration
        if api_base:
            self._api_base = api_base

    def get_crypto_state(self) -> dict[str, str]:
        """Get the ECDH crypto state for serialization.

        Returns dict with private_key and server_public_key as hex strings.
        """
        private_key_bytes = self._private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return {
            "private_key": private_key_bytes.hex(),
            "server_public_key": self._server_public_key_hex or "",
        }

    def restore_crypto_state(
        self, private_key_hex: str, server_public_key_hex: str
    ) -> bool:
        """Restore ECDH crypto state from serialized data.

        Returns True if successful, False if data is invalid/missing.
        """
        if not private_key_hex or not server_public_key_hex:
            return False

        try:
            # Restore private key
            private_key_bytes = bytes.fromhex(private_key_hex)
            loaded_key = serialization.load_der_private_key(
                private_key_bytes, password=None, backend=default_backend()
            )
            if not isinstance(loaded_key, EllipticCurvePrivateKey):
                return False
            self._private_key = loaded_key
            self._public_key = self._private_key.public_key()
            self._client_public_bytes = self._public_key.public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint,
            )

            # Recompute login shared secret (for future logins if needed)
            server_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(), SERVER_PUBLIC_KEY
            )
            self._login_shared_secret = self._private_key.exchange(
                ec.ECDH(), server_public_key
            )

            # Restore response shared secret
            self._server_public_key_hex = server_public_key_hex
            server_public_key_bytes = bytes.fromhex(server_public_key_hex)
            server_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(), server_public_key_bytes
            )
            self._response_shared_secret = self._private_key.exchange(
                ec.ECDH(), server_public_key
            )
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Failed to restore crypto state: %s", err)
            return False

        _LOGGER.debug("Restored ECDH crypto state")
        return True

    async def _async_get_api_base(self) -> str:
        """Get the regional API base URL."""
        if self._api_base:
            return self._api_base

        url = f"{DOMAIN_LOOKUP_URL}/{self._country}"
        headers = {**DEFAULT_HEADERS, "Country": self._country}

        try:
            async with self._session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    raise CannotConnectError(f"Failed to get API domain: {resp.status}")

                data = await resp.json()
                if data.get("code") != 0:
                    raise CannotConnectError(
                        f"Failed to get API domain: {data.get('msg')}"
                    )

                domain = data.get("data", {}).get("domain")
                if not domain:
                    raise CannotConnectError("No domain in response")

                self._api_base = f"https://{domain}"
                _LOGGER.debug("Using API base: %s", self._api_base)
                return self._api_base

        except ClientError as err:
            raise CannotConnectError(f"Connection error: {err}") from err

    async def async_authenticate(
        self, captcha_id: str | None = None, captcha_code: str | None = None
    ) -> None:
        """Authenticate using the v2 encrypted API.

        Args:
            captcha_id: CAPTCHA ID from previous failed attempt.
            captcha_code: User-provided CAPTCHA solution.
        """
        api_base = await self._async_get_api_base()

        # Encrypt password using login shared secret
        encrypted_password = encrypt_api_data(
            self._password, self._login_shared_secret
        )

        payload: dict[str, Any] = {
            "ab": self._country,
            "client_secret_info": {"public_key": self._client_public_bytes.hex()},
            "enc": 0,
            "email": self._email,
            "password": encrypted_password,
        }

        # Add CAPTCHA data if provided
        if captcha_id and captcha_code:
            payload["captcha_id"] = captcha_id
            payload["answer"] = captcha_code

        headers = {**DEFAULT_HEADERS, "Country": self._country}

        try:
            async with self._session.post(
                f"{api_base}/v2/passport/login_sec",
                headers=headers,
                json=payload,
            ) as resp:
                # Check for non-JSON response
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    text = await resp.text()
                    _LOGGER.debug("Non-JSON response: %s", text[:200])
                    raise CannotConnectError(
                        f"Unexpected response type: {content_type}"
                    )

                data = await resp.json()
                _LOGGER.debug(
                    "Login response: code=%s, msg=%s",
                    data.get("code"),
                    data.get("msg"),
                )

                # Check for CAPTCHA requirement (code 100032)
                code = data.get("code", 0)
                if code == 100032:
                    captcha_data = data.get("data", {})
                    raise CaptchaRequiredError(
                        "CAPTCHA verification required",
                        captcha_id=captcha_data.get("captcha_id", ""),
                        captcha_image=captcha_data.get("item"),
                    )

                raise_on_error(data)

                auth_data = data.get("data", {})
                self._token = auth_data.get("auth_token")

                if not self._token:
                    raise InvalidCredentialsError("No auth token received")

                # Set token expiration
                expires_at = auth_data.get("token_expires_at")
                if expires_at:
                    self._token_expiration = datetime.fromtimestamp(expires_at)

                # Update API base if different domain provided
                domain = auth_data.get("domain")
                if domain:
                    self._api_base = f"https://{domain}"
                    _LOGGER.debug("Updated API base: %s", self._api_base)

                # Compute shared secret for decrypting responses
                server_secret_info = auth_data.get("server_secret_info", {})
                server_public_key_hex = server_secret_info.get("public_key")
                if server_public_key_hex:
                    self._server_public_key_hex = server_public_key_hex
                    server_public_key_bytes = bytes.fromhex(server_public_key_hex)
                    server_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                        ec.SECP256R1(), server_public_key_bytes
                    )
                    self._response_shared_secret = self._private_key.exchange(
                        ec.ECDH(), server_public_key
                    )
                    _LOGGER.debug("Computed response decryption key")

                self._retry_on_401 = False

        except ClientError as err:
            raise CannotConnectError(f"Connection error: {err}") from err

    def _decrypt_response_data(self, data: str) -> Any:
        """Decrypt and parse response data."""
        if not self._response_shared_secret:
            raise EufySecurityError("No decryption key available")

        decrypted = decrypt_api_data(data, self._response_shared_secret)
        return json_module.loads(decrypted)

    async def async_get_latest_events(self) -> dict[str, dict[str, Any]]:
        """Get the latest events for all cameras to extract thumbnail URLs.

        Returns a dict mapping device_sn to the latest event data.
        """
        # Get events from the last 7 days
        end_time = int(time.time())
        start_time = end_time - (7 * 24 * 60 * 60)

        try:
            resp = await self.async_request(
                "post",
                "v2/event/app/get_all_history_record",
                data={
                    "device_sn": "",  # All devices
                    "station_sn": "",  # All stations
                    "start_time": start_time,
                    "end_time": end_time,
                    "num": 100,  # Get up to 100 recent events
                    "storage": 0,  # All storage types
                    "is_favorite": False,
                    "shared": False,
                },
            )
        except EufySecurityError as err:
            _LOGGER.debug("Failed to get event history: %s", err)
            return {}

        raw_data = resp.get("data")
        events_data: list[dict[str, Any]]
        if raw_data and isinstance(raw_data, str):
            # Encrypted response - decrypt it
            decrypted = self._decrypt_response_data(raw_data)
            # The decrypted data might be null/None, a dict, or a list
            if decrypted is None:
                events_data = []
            elif isinstance(decrypted, dict):
                events_data = decrypted.get("data", []) or []
            elif isinstance(decrypted, list):
                events_data = decrypted
            else:
                events_data = []
        elif raw_data and isinstance(raw_data, list):
            events_data = raw_data
        elif raw_data and isinstance(raw_data, dict):
            events_data = raw_data.get("data", []) or []
        else:
            events_data = []

        # Build a dict of device_sn -> latest event with pic_url
        latest_events: dict[str, dict[str, Any]] = {}
        for event in events_data:
            device_sn = event.get("device_sn")
            pic_url = event.get("pic_url")
            if device_sn and pic_url:
                # Only update if this is a newer event or first event
                if device_sn not in latest_events:
                    latest_events[device_sn] = event
                    _LOGGER.debug(
                        "Found thumbnail for %s: %s",
                        device_sn,
                        pic_url[:80] if len(pic_url) > 80 else pic_url,
                    )

        return latest_events

    async def async_update_device_info(self) -> None:
        """Get the latest device info."""
        # Get devices/cameras using v2 endpoint
        devices_resp = await self.async_request("post", "v2/app/get_devs_list")

        # The response data may be encrypted
        raw_data = devices_resp.get("data")
        if raw_data and isinstance(raw_data, str):
            # Encrypted response - decrypt it
            device_data = self._decrypt_response_data(raw_data)
        elif raw_data and isinstance(raw_data, list):
            # Unencrypted response
            device_data = raw_data
        else:
            device_data = []

        for device_info in device_data:
            device_sn = device_info.get("device_sn")
            if not device_sn:
                continue

            if device_sn in self.cameras:
                # Update existing camera
                self.cameras[device_sn].camera_info = device_info
            else:
                # Create new camera
                self.cameras[device_sn] = Camera(
                    _api=self,
                    camera_info=device_info,
                )

        # Get stations/hubs
        try:
            stations_resp = await self.async_request("post", "v2/app/get_hub_list")
            raw_stations = stations_resp.get("data")

            if raw_stations and isinstance(raw_stations, str):
                stations_data = self._decrypt_response_data(raw_stations)
            elif raw_stations and isinstance(raw_stations, list):
                stations_data = raw_stations
            else:
                stations_data = []

            for station_data in stations_data:
                station = Station(
                    serial=station_data.get("station_sn", ""),
                    name=station_data.get("station_name", "Unknown"),
                    model=station_data.get("station_model", "Unknown"),
                )
                self.stations[station.serial] = station
        except EufySecurityError:
            # Stations list may not be available for all accounts
            pass

        # Get latest events to populate camera thumbnails
        latest_events = await self.async_get_latest_events()
        for device_sn, event_data in latest_events.items():
            if device_sn in self.cameras:
                self.cameras[device_sn].update_event_data(event_data)

    async def async_request(
        self,
        method: str,
        endpoint: str,
        *,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        skip_auth: bool = False,
    ) -> dict[str, Any]:
        """Make a request to the API."""
        api_base = await self._async_get_api_base()

        # Check token expiration and refresh if needed
        if (
            not skip_auth
            and self._token_expiration
            and datetime.now() >= self._token_expiration
        ):
            _LOGGER.info("Access token expired; fetching a new one")
            self._token = None
            self._token_expiration = None
            await self.async_authenticate()

        url = f"{api_base}/{endpoint}"

        request_headers = {**DEFAULT_HEADERS, "Country": self._country}
        if headers:
            request_headers.update(headers)
        if self._token and not skip_auth:
            request_headers["x-auth-token"] = self._token

        try:
            async with self._session.request(
                method, url, headers=request_headers, json=data
            ) as resp:
                # Check for non-JSON response (blocked/rate limited)
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    text = await resp.text()
                    _LOGGER.debug("Non-JSON response from %s: %s", endpoint, text[:200])
                    raise CannotConnectError(
                        f"Unexpected response type from {endpoint}: {content_type}"
                    )

                resp.raise_for_status()
                resp_data: dict[str, Any] = await resp.json(content_type=None)

                if not resp_data:
                    raise RequestError(f"No response from {endpoint}")

                raise_on_error(resp_data)
                return resp_data

        except ClientError as err:
            error_str = str(err)
            if "401" in error_str:
                if self._retry_on_401:
                    raise InvalidCredentialsError(
                        "Authentication failed after retry"
                    ) from err

                self._retry_on_401 = True
                _LOGGER.info("Got 401, attempting re-authentication")
                await self.async_authenticate()
                return await self.async_request(
                    method, endpoint, headers=headers, data=data
                )
            raise CannotConnectError(f"Request error: {err}") from err


async def async_login(
    email: str,
    password: str,
    session: ClientSession,
    country: str = "US",
    captcha_id: str | None = None,
    captcha_code: str | None = None,
    api: EufySecurityAPI | None = None,
) -> EufySecurityAPI:
    """Login and return an authenticated API client.

    Args:
        email: Eufy account email.
        password: Eufy account password.
        session: aiohttp client session.
        country: Country code (default US).
        captcha_id: CAPTCHA ID from previous failed attempt.
        captcha_code: User-provided CAPTCHA solution.
        api: Existing API instance to reuse (for CAPTCHA retry with same ECDH keys).

    Raises:
        CaptchaRequiredError: When CAPTCHA verification is needed (includes API instance).
        InvalidCredentialsError: When credentials are invalid.
        CannotConnectError: When connection fails.
    """
    if api is None:
        api = EufySecurityAPI(session, email, password, country)
    try:
        await api.async_authenticate(captcha_id, captcha_code)
    except CaptchaRequiredError as err:
        # Re-raise with API instance so caller can retry with same ECDH keys
        raise CaptchaRequiredError(
            str(err),
            captcha_id=err.captcha_id,
            captcha_image=err.captcha_image,
            api=api,
        ) from err
    await api.async_update_device_info()
    return api
