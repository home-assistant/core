"""Client for the Telldus Live cloud API and the local Tellstick API.

Derived from the public domain ``tellduslive`` package (0.10.12).
"""

from collections import deque
from collections.abc import Iterator
from datetime import datetime, timedelta
import logging
import socket
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import requests
from requests_oauthlib import OAuth1Session

from homeassistant.util import dt as dt_util

from .const import (
    DIM,
    DOWN,
    METHODS,
    REQUEST_TIMEOUT,
    STOP,
    SUPPORTED_METHODS,
    SUPPORTS_LOCAL_API,
    TELLDUS_LIVE_ACCESS_TOKEN_URL,
    TELLDUS_LIVE_API_URL,
    TELLDUS_LIVE_AUTHORIZE_URL,
    TELLDUS_LIVE_REQUEST_TOKEN_URL,
    TELLDUS_LOCAL_API_URL,
    TELLDUS_LOCAL_DISCOVERY_PORT,
    TELLDUS_LOCAL_REFRESH_TOKEN_URL,
    TELLDUS_LOCAL_REQUEST_TOKEN_URL,
    TURNOFF,
    TURNON,
    UP,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_APPLICATION_NAME = "tellduslive"
HTTP_TOO_MANY_REQUESTS = 429
TOKEN_REFRESH_AGE = timedelta(hours=12)
RESPONSE_WINDOW = 3600


class TelldusLiveError(OSError):
    """Error communicating with Telldus Live."""


class TelldusLiveRateLimitError(TelldusLiveError):
    """The API answered with 429 Too Many Requests."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.retry_after = retry_after


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header given in seconds."""
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def supports_local_api(device: str) -> bool:
    """Return true if the device supports local access."""
    return any(dev in device for dev in SUPPORTS_LOCAL_API)


class LocalAPISession(requests.Session):
    """Connect directly to the device."""

    def __init__(
        self, host: str, application: str | None, access_token: str | None = None
    ) -> None:
        """Initialize the session."""
        super().__init__()
        self.url = TELLDUS_LOCAL_API_URL.format(host=host)
        self._host = host
        self._hub_id: str | None = None
        self._application = application or DEFAULT_APPLICATION_NAME
        self.request_token: str | None = None
        self.token_timestamp: datetime | None = None
        self.access_token = access_token
        if access_token:
            self.headers.update({"Authorization": f"Bearer {access_token}"})
            self.refresh_access_token()

    def discovery_info(self) -> list[dict[str, str]]:
        """Retrieve information from the discovery socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        try:
            sock.sendto(b"D", (self._host, TELLDUS_LOCAL_DISCOVERY_PORT))
            data, (address, _) = sock.recvfrom(1024)
        except TimeoutError:
            _LOGGER.warning("Socket timeout trying to read info from Tellstick")
            return []
        finally:
            sock.close()
        # product, mac, activation code, version
        entry = data.decode("ascii").split(":")
        if len(entry) != 4:
            return []
        ret = [
            {
                "name": address,
                "type": entry[0],
                "id": entry[1],
                "version": entry[3],
            }
        ]
        _LOGGER.debug("Discovered hub: %s", ret)
        self._hub_id = entry[1]
        return ret

    @property
    def hub_id(self) -> str | None:
        """Return the hub id."""
        return self._hub_id

    @property
    def authorize_url(self) -> str | None:
        """Retrieve URL for authorization."""
        try:
            response = self.put(
                TELLDUS_LOCAL_REQUEST_TOKEN_URL.format(host=self._host),
                data={"app": self._application},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            self.request_token = result.get("token")
            return result.get("authUrl")
        except (OSError, ValueError) as err:
            _LOGGER.error("Failed to retrieve authorization URL: %s", err)
        return None

    def authorize(self) -> bool | None:
        """Perform authorization."""
        try:
            response = self.get(
                TELLDUS_LOCAL_REQUEST_TOKEN_URL.format(host=self._host),
                params={"token": self.request_token},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            if "token" in result:
                self.access_token = result["token"]
                self.headers.update({"Authorization": f"Bearer {self.access_token}"})
                self.token_timestamp = dt_util.naive_now()
                _LOGGER.debug(
                    "Token expires %s", datetime.fromtimestamp(result.get("expires"))
                )
                return True
        except OSError as err:
            _LOGGER.error("Failed to authorize: %s", err)
        return None

    def refresh_access_token(self) -> bool | None:
        """Refresh the API token."""
        try:
            response = self.get(
                TELLDUS_LOCAL_REFRESH_TOKEN_URL.format(host=self._host),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            self.access_token = result.get("token")
            self.headers.update({"Authorization": f"Bearer {self.access_token}"})
            self.token_timestamp = dt_util.naive_now()
            _LOGGER.debug(
                "Token expires %s", datetime.fromtimestamp(result.get("expires"))
            )
        except OSError as err:
            _LOGGER.error("Failed to refresh access token: %s", err)
            return None
        return True

    @property
    def authorized(self) -> str | None:
        """Return the access token if successfully authorized."""
        return self.access_token

    def maybe_refresh_token(self) -> None:
        """Refresh the access token if expired."""
        if (
            self.token_timestamp
            and dt_util.naive_now() - self.token_timestamp > TOKEN_REFRESH_AGE
        ):
            self.refresh_access_token()


class LiveAPISession(OAuth1Session):
    """Connection to the cloud service."""

    def __init__(
        self,
        public_key: str,
        private_key: str,
        token: str | None = None,
        token_secret: str | None = None,
        application: str | None = None,
    ) -> None:
        """Initialize the session."""
        super().__init__(public_key, private_key, token, token_secret)
        self.url = TELLDUS_LIVE_API_URL
        self.access_token: str | None = None
        self.access_token_secret: str | None = None
        if application:
            self.headers.update({"X-Application": application})

    @property
    def hub_id(self) -> None:
        """Return the hub id; not applicable for the cloud."""
        return None

    @property
    def authorize_url(self) -> str | None:
        """Retrieve URL for authorization."""
        _LOGGER.debug("Fetching request token")
        try:
            self.fetch_request_token(
                TELLDUS_LIVE_REQUEST_TOKEN_URL, timeout=REQUEST_TIMEOUT
            )
            _LOGGER.debug("Got request token")
            return self.authorization_url(TELLDUS_LIVE_AUTHORIZE_URL)
        except (OSError, ValueError) as err:
            _LOGGER.error("Failed to retrieve authorization URL: %s", err)
        return None

    def authorize(self) -> bool | None:
        """Perform authorization."""
        try:
            _LOGGER.debug("Fetching access token")
            token = self._fetch_token(
                TELLDUS_LIVE_ACCESS_TOKEN_URL, timeout=REQUEST_TIMEOUT
            )
            _LOGGER.debug("Got access token")
            self.access_token = token["oauth_token"]
            self.access_token_secret = token["oauth_token_secret"]
        except (OSError, ValueError) as err:
            _LOGGER.error("Failed to authorize: %s", err)
            return None
        _LOGGER.debug("Authorized: %s", self.authorized)
        return self.authorized

    def maybe_refresh_token(self) -> None:
        """Do nothing; cloud tokens do not expire."""

    def discovery_info(self) -> list[dict[str, str]]:
        """Return no hubs; discovery is local only."""
        return []


class Session:
    """Telldus Live session."""

    def __init__(
        self,
        public_key: str | None = None,
        private_key: str | None = None,
        token: str | None = None,
        token_secret: str | None = None,
        host: str | None = None,
        application: str | None = None,
    ) -> None:
        """Initialize the session."""
        if not ((public_key and private_key) or host):
            raise ValueError("Missing configuration")

        self._state: dict[str, dict[str, Any]] = {}
        self._ok_responses: deque[float] = deque()
        self._sensors_empty = False
        self._session: LocalAPISession | LiveAPISession
        if host:
            self._session = LocalAPISession(host, application, token)
        else:
            if TYPE_CHECKING:
                assert public_key and private_key
            self._session = LiveAPISession(
                public_key, private_key, token, token_secret, application
            )

    @property
    def authorize_url(self) -> str | None:
        """Retrieve URL for authorization."""
        return self._session.authorize_url

    def authorize(self) -> bool | None:
        """Perform authorization."""
        return self._session.authorize()

    @property
    def access_token(self) -> str | None:
        """Return the access token."""
        return self._session.access_token

    @property
    def is_authorized(self) -> bool:
        """Return true if successfully authorized."""
        return bool(self._session.authorized)

    @property
    def access_token_secret(self) -> str | None:
        """Return the token secret."""
        return getattr(self._session, "access_token_secret", None)

    def _device(self, device_id: str) -> dict[str, Any] | None:
        """Return the raw representation of a device."""
        return self._state.get(device_id)

    def _request(self, path: str, **params: Any) -> dict[str, Any]:
        """Send a request to the API.

        Raises TelldusLiveError, or TelldusLiveRateLimitError on HTTP 429.
        """
        try:
            self._session.maybe_refresh_token()
            url = urljoin(self._session.url, path)
            _LOGGER.debug("Request %s %s", url, params)
            response = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code == HTTP_TOO_MANY_REQUESTS:
                raise TelldusLiveRateLimitError(
                    "Rate limited by Telldus Live",
                    _parse_retry_after(response.headers.get("Retry-After")),
                )
            response.raise_for_status()
            result = response.json()
        except TelldusLiveError:
            raise
        except (OSError, ValueError) as err:
            raise TelldusLiveError(str(err)) from err
        _LOGGER.debug("Response %s %s", response.status_code, result)
        if "error" in result:
            raise TelldusLiveError(str(result["error"]))
        self._ok_responses.append(time.monotonic())
        return result

    def ok_responses_last_hour(self) -> int:
        """Return the number of OK API responses during the last 60 minutes."""
        cutoff = time.monotonic() - RESPONSE_WINDOW
        while self._ok_responses and self._ok_responses[0] < cutoff:
            self._ok_responses.popleft()
        return len(self._ok_responses)

    def execute(self, method: str, **params: Any) -> bool:
        """Make a request and return whether it was successful."""
        try:
            response = self._request(method, **params)
        except TelldusLiveError as err:
            _LOGGER.warning("Failed request: %s", err)
            return False
        return response.get("status") == "success"

    def _request_devices(self) -> list[dict[str, Any]]:
        """Request list of devices from server."""
        res = self._request(
            "devices/list", supportedMethods=SUPPORTED_METHODS, includeIgnored=0
        )
        return res.get("device", [])

    def _request_sensors(self) -> list[dict[str, Any]]:
        """Request list of sensors from server."""
        res = self._request(
            "sensors/list", includeValues=1, includeScale=1, includeIgnored=0
        )
        return res.get("sensor", [])

    def update(self) -> None:
        """Update all devices and sensors from server.

        Sensors are prefixed with '_' since devices and sensors do not share
        a namespace and ids can collide. If one of the requests fails, the part
        of the state it covers is kept and the first error is raised after
        the other part has been updated.
        """
        errors: list[TelldusLiveError] = []
        new_state: dict[str, dict[str, Any]] = {}
        for is_sensor, request in (
            (False, self._request_devices),
            (True, self._request_sensors),
        ):
            if is_sensor and self._sensors_empty:
                continue
            try:
                items = request()
            except TelldusLiveRateLimitError:
                raise
            except TelldusLiveError as err:
                errors.append(err)
                new_state.update(
                    {
                        key: value
                        for key, value in self._state.items()
                        if key.startswith("_") == is_sensor
                    }
                )
                continue
            if is_sensor and not items:
                _LOGGER.info(
                    "No sensors found, not polling sensors until Home Assistant restarts"
                )
                self._sensors_empty = True
            new_state.update(
                {
                    "_" * is_sensor + str(item["id"]): item
                    for item in items
                    if item["name"] and not (is_sensor and "data" not in item)
                }
            )
        self._state = new_state
        if errors:
            raise errors[0]

    def request_info(self, device_id: str) -> dict[str, Any]:
        """Request device info."""
        return self._request("device/info", id=device_id)

    def dump_state(self) -> dict[str, dict[str, Any]]:
        """Return the known devices and sensors for persisting."""
        return self._state

    def load_state(self, state: dict[str, dict[str, Any]]) -> None:
        """Restore previously persisted devices and sensors."""
        self._state = state

    @property
    def hub_id(self) -> str | None:
        """Return hub id."""
        return self._session.hub_id

    def get_clients(self) -> list[dict[str, Any]]:
        """Request list of clients (Telldus devices) from server."""
        if isinstance(self._session, LocalAPISession):
            return self._session.discovery_info()
        return self._request("clients/list").get("client", [])

    def device(self, device_id: str) -> Device:
        """Return a device object."""
        return Device(self, device_id)

    @property
    def devices(self) -> Iterator[Device]:
        """Return all known devices."""
        return (self.device(device_id) for device_id in self.device_ids)

    @property
    def device_ids(self) -> Any:
        """Return the known device ids."""
        return self._state.keys()


class Device:
    """Telldus Live device."""

    def __init__(self, session: Session, device_id: str) -> None:
        """Initialize the device."""
        self._session = session
        self._device_id = device_id

    def __getattr__(self, name: str) -> Any:
        """Return raw device attributes."""
        if self.device and name in (
            "name",
            "state",
            "battery",
            "model",
            "protocol",
            "lastUpdated",
            "methods",
            "data",
            "sensorId",
        ):
            return self.device.get(name)
        return None

    @property
    def device(self) -> dict[str, Any] | None:
        """Return the raw representation of the device."""
        return self._session._device(self._device_id)  # noqa: SLF001

    @property
    def device_id(self) -> str:
        """Return the id of the device."""
        return self._device_id

    def _execute(self, command: int, **params: Any) -> bool:
        """Send command to server and update local state."""
        params.update(id=self._device_id)
        if self._session.execute(f"device/{METHODS[command]}", **params):
            self.device["state"] = command  # type: ignore[index]
            return True
        return False

    @property
    def is_sensor(self) -> bool:
        """Return true if this is a sensor."""
        return "data" in self.device  # type: ignore[operator]

    @property
    def statevalue(self) -> Any:
        """Return the state value of the device."""
        val = self.device.get("statevalue")  # type: ignore[union-attr]
        return val if val and val != "unde" else 0

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.state in (TURNON, DIM)

    @property
    def is_down(self) -> bool:
        """Return true if device is down."""
        return self.state == DOWN

    @property
    def dim_level(self) -> int | None:
        """Return current dim level."""
        try:
            return int(self.statevalue)
        except TypeError, ValueError:
            return None

    def info(self) -> dict[str, Any] | None:
        """Retrieve device info."""
        if self.is_sensor:
            res = self.device
        else:
            res = self._session.request_info(self._device_id)
        if res and "client" not in res:
            res["client"] = self._session.hub_id
        return res or None

    def turn_on(self) -> bool:
        """Turn device on."""
        return self._execute(TURNON)

    def turn_off(self) -> bool:
        """Turn device off."""
        return self._execute(TURNOFF)

    def dim(self, level: int) -> bool:
        """Dim device."""
        if self._execute(DIM, level=level):
            self.device["statevalue"] = level  # type: ignore[index]
            return True
        return False

    def up(self) -> bool:
        """Pull device up."""
        return self._execute(UP)

    def down(self) -> bool:
        """Pull device down."""
        return self._execute(DOWN)

    def stop(self) -> bool:
        """Stop device."""
        return self._execute(STOP)

    @property
    def items(self) -> Iterator[SensorItem] | list[SensorItem]:
        """Return sensor items for sensor."""
        return (SensorItem(item) for item in self.data) if self.data else []

    def item(self, name: str, scale: int | str) -> SensorItem | None:
        """Return sensor item."""
        return next(
            (
                item
                for item in self.items
                if item.name == name and int(item.scale) == int(scale)
            ),
            None,
        )

    def value(self, name: str, scale: int | str) -> Any:
        """Return value of sensor item."""
        return self.item(name, scale).value  # type: ignore[union-attr]


class SensorItem:
    """Reference to a sensor data item."""

    name: str
    value: Any
    scale: int | str

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize from raw data."""
        vars(self).update(data)
