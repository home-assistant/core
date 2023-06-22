"""Support for Vodafone Station."""
import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import html
from http.cookies import SimpleCookie
import re
import urllib.parse

import aiohttp

from homeassistant.components.device_tracker import DEFAULT_CONSIDER_HOME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import _LOGGER, DOMAIN


@dataclass
class Device:
    """Vodafone Station device class."""

    connected: bool
    connection_type: str
    ip_address: str
    name: str
    mac: str
    wifi: str


class VodafoneStationDeviceInfo:
    """Representation of a device connected to the Vodafone Station."""

    def __init__(self, mac: str, name: str | None = None) -> None:
        """Initialize device info."""
        self._connected = False
        self._connection_type: str | None = None
        self._ip_address: str | None = None
        self._last_activity: datetime | None = None
        self._mac = mac
        self._name = name
        self._wifi: str | None = None

    def update(
        self,
        dev_info: Device,
        consider_home: float = DEFAULT_CONSIDER_HOME.total_seconds(),
    ) -> None:
        """Update device info."""
        utc_point_in_time = dt_util.utcnow()

        if self._last_activity:
            consider_home_evaluated = (
                utc_point_in_time - self._last_activity
            ).total_seconds() < consider_home
        else:
            consider_home_evaluated = dev_info.connected

        if not self._name:
            self._name = dev_info.name or self._mac.replace(":", "_")

        self._connected = dev_info.connected or consider_home_evaluated

        if dev_info.connected:
            self._last_activity = utc_point_in_time

        self._connection_type = dev_info.connection_type
        self._ip_address = dev_info.ip_address
        self._wifi = dev_info.wifi

    @property
    def connection_type(self) -> str:
        """Return connected status."""
        return self._connection_type or ""

    @property
    def is_connected(self) -> bool:
        """Return connected status."""
        return self._connected

    @property
    def mac_address(self) -> str:
        """Get MAC address."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Get Name."""
        return self._name

    @property
    def ip_address(self) -> str | None:
        """Get IP address."""
        return self._ip_address

    @property
    def last_activity(self) -> datetime | None:
        """Return device last activity."""
        return self._last_activity

    @property
    def wifi(self) -> str | None:
        """Return device WIFi connection."""
        return self._wifi


class VodafoneStationApi(DataUpdateCoordinator):
    """Queries router running Vodafone Station firmware."""

    def __init__(
        self, host: str, ssl: bool, username: str, password: str, hass: HomeAssistant
    ) -> None:
        """Initialize the scanner."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=30),
        )

        self.host = host
        self.protocol = "https" if ssl else "http"
        self.username = username
        self.password = password
        self.hass = hass
        self.base_url = f"{self.protocol}://{self.host}"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.5",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/login.html",
            "DNT": "1",
        }
        jar = aiohttp.CookieJar(unsafe=True)
        self.session = aiohttp.ClientSession(cookie_jar=jar)
        self.csrf_token: str = ""
        self.encryption_key: str = ""
        self._unique_id: str | None = None
        self._devices: dict[str, VodafoneStationDeviceInfo] = {}
        self._data: dict[str, str] = {}
        self._on_close: list[Callable] = []

    async def _get_csrf_token(self) -> None:
        """Load login page to get csrf token."""

        url = f"{self.base_url}/login.html"
        reply = await self.session.get(
            url,
            headers=self.headers,
            timeout=10,
            verify_ssl=False,
            allow_redirects=False,
        )
        reply_text = await reply.text()
        tokens = re.search("(?<=csrf_token = ')[^']+", reply_text)
        if not tokens:
            return None
        self.csrf_token = tokens.group(0)
        _LOGGER.debug("csrf_token: <%s>", self.csrf_token)

    async def _get_user_lang(self) -> None:
        """Load user_lang page to get."""

        timestamp = datetime.now().strftime("%s")
        url = f"{self.base_url}/data/user_lang.json?_={timestamp}&csrf_token={self.csrf_token}"
        reply = await self.session.get(
            url,
            headers=self.headers,
            timeout=10,
            verify_ssl=False,
            allow_redirects=False,
        )

        j = await reply.json(content_type="text/html")
        user_obj = {}
        for item in j:
            key = list(item.keys())[0]
            val = list(item.values())[0]
            user_obj[key] = val

        self.encryption_key = user_obj["encryption_key"]
        _LOGGER.debug("encryption_key: <%s>", self.encryption_key)

    async def _encrypt_string(self, credential: str) -> str:
        """Encrypt username or password for login."""

        credential = urllib.parse.quote(credential)
        credential = html.unescape(credential)
        hash1_str = hmac.new(
            bytes("$1$SERCOMM$", "latin-1"),
            msg=bytes(credential, "latin-1"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.new(
            bytes(self.encryption_key, "latin-1"),
            msg=bytes(hash1_str, "latin-1"),
            digestmod=hashlib.sha256,
        ).hexdigest()

    async def _set_cookie(self) -> None:
        """Enable required session cookie."""
        self.session.cookie_jar.update_cookies(
            SimpleCookie(f"domain={self.host}; name=login_uid; value=1;")
        )

    async def _reset(self) -> bool:
        """Reset page content before loading."""

        payload = {"chk_sys_busy": ""}
        timestamp = datetime.now().strftime("%s")
        url = f"{self.base_url}/data/reset.json?_={timestamp}&csrf_token={self.csrf_token}"
        reply = await self.session.post(
            url,
            data=payload,
            headers=self.headers,
            timeout=10,
            verify_ssl=False,
            allow_redirects=False,
        )

        return reply.status == 200

    async def _overview(self) -> dict:
        """Load overview page information."""
        _LOGGER.debug("Getting overview for host %s", self.host)
        timestamp = datetime.now().strftime("%s")
        url = f"{self.base_url}/data/overview.json?_={timestamp}&csrf_token={self.csrf_token}"

        reply = await self.session.get(
            url,
            headers=self.headers,
            timeout=10,
            verify_ssl=False,
            allow_redirects=True,
        )
        reply_json = await reply.json(content_type="text/html")
        _LOGGER.debug("Full Response (overview): %s", reply_json)
        return reply_json

    async def _user_data(self) -> dict:
        """Load user_data page information."""
        _LOGGER.debug("Getting user_data for host %s", self.host)
        timestamp = datetime.now().strftime("%s")
        url = f"{self.base_url}/data/user_data.json?_={timestamp}&csrf_token={self.csrf_token}"

        reply = await self.session.get(
            url,
            headers=self.headers,
            timeout=10,
            verify_ssl=False,
            allow_redirects=False,
        )
        reply_json = await reply.json(content_type="text/html")
        _LOGGER.debug("Full Response (user_data): %s", reply_json)
        return reply_json

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    async def _async_update_data(self) -> bool:
        """Update router data."""
        _LOGGER.debug("Polling Vodafone Station host: %s", self.host)
        try:
            logged = await self.login()
        except (asyncio.exceptions.TimeoutError, aiohttp.ClientConnectorError) as err:
            _LOGGER.warning("Connection error for %s", self.host)
            raise UpdateFailed(f"Error fetching data: {repr(err)}") from err

        if not logged:
            raise ConfigEntryAuthFailed

        self._devices = await self._get_all_devices()
        self._data = await self._user_data()

        return True

    async def _get_all_devices(self) -> dict:
        """Get all connected devices."""

        _LOGGER.debug("Getting all devices for host %s", self.host)
        data = await self._overview()
        kv_tuples = [(list(v.keys())[0], (list(v.values())[0])) for v in data]
        key_values = {}
        for entry in kv_tuples:
            key_values[entry[0]] = entry[1]

        _LOGGER.debug("Data retrieved (key_values): %s", key_values)
        if (
            "wifi_user" not in key_values
            and "wifi_guest" not in key_values
            and "ethernet" not in key_values
        ):
            _LOGGER.info("No device in response from %s", self.host)
            return self._devices

        # 'on|smartphone|Telefono Nora (2.4GHz)|00:0a:f5:6d:8b:38|192.168.1.128||2.4G;'
        arr_devices = []
        arr_wifi_user = key_values["wifi_user"].split(";")
        arr_wifi_user = filter(lambda x: x.strip() != "", arr_wifi_user)
        arr_wifi_user = ["Wifi (Main)|" + dev for dev in arr_wifi_user]
        arr_wifi_guest = key_values["wifi_guest"].split(";")
        arr_wifi_guest = filter(lambda x: x.strip() != "", arr_wifi_guest)
        arr_wifi_guest = ["[Wifi (Guest)|" + dev for dev in arr_wifi_guest]
        arr_devices.append(arr_wifi_user)
        arr_devices.append(arr_wifi_guest)
        arr_ethernet = key_values["ethernet"].split(";")
        arr_ethernet = filter(lambda x: x.strip() != "", arr_ethernet)
        arr_ethernet = ["Ethernet|on|" + dev + "|||" for dev in arr_ethernet]
        arr_devices.append(arr_ethernet)
        arr_devices = [item for sublist in arr_devices for item in sublist]
        _LOGGER.debug("Array of devices: %s", arr_devices)

        for device_line in arr_devices:
            device_fields = device_line.split("|")
            try:
                dev_info = Device(
                    connection_type=device_fields[0],
                    connected=device_fields[1] == "on",
                    name=device_fields[3],
                    mac=device_fields[4],
                    ip_address=device_fields[5],
                    wifi=device_fields[7],
                )
                dev = VodafoneStationDeviceInfo(dev_info.mac, dev_info.name)
                dev.update(dev_info)
                self._devices[dev_info.mac] = dev
            except (KeyError, IndexError):
                _LOGGER.warning("Error processing line: %s", device_line)

        return self._devices

    async def login(self) -> bool:
        """Router login."""
        _LOGGER.debug("Logging into %s", self.host)
        try:
            await self._get_csrf_token()
        except (asyncio.exceptions.TimeoutError,) as exc:
            _LOGGER.warning("No response from %s", self.host)
            raise exc
        except aiohttp.ClientConnectorError as exc:
            _LOGGER.warning("Connection error for %s", self.host)
            raise exc

        await self._get_user_lang()
        await self._set_cookie()
        await self._reset()

        username = (
            await self._encrypt_string(self.username)
            if self.protocol == "https"
            else self.username
        )
        payload = {
            "LoginName": username,
            "LoginPWD": await self._encrypt_string(self.password),
        }
        timestamp = datetime.now().strftime("%s")
        url = f"{self.base_url}/data/login.json?_={timestamp}&csrf_token={self.csrf_token}"
        reply = await self.session.post(
            url,
            data=payload,
            headers=self.headers,
            timeout=10,
            verify_ssl=False,
            allow_redirects=True,
        )
        return reply.status == 200

    async def logout(self) -> None:
        """Router logout."""
        self.session.cookie_jar.clear()
        await self.session.close()

    @property
    def devices(self) -> dict[str, VodafoneStationDeviceInfo]:
        """Return a list of devices."""
        return self._devices

    @property
    def signal_device_new(self) -> str:
        """Event specific per Vodafone Station entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._unique_id}"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Vodafone Station entry to signal updates in devices."""
        return f"{DOMAIN}-device-update-{self._unique_id}"
