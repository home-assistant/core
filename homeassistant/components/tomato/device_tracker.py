"""Support for Tomato routers."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import json
import logging
import re
from typing import Any

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    ScannerEntity,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_HTTP_ID = "http_id"

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=12)

SIGNAL_TOMATO_UPDATE = "tomato_update"

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): vol.Any(cv.boolean, cv.isfile),
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_HTTP_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tomato device tracker platform."""
    scanner = TomatoData(config)

    success = await hass.async_add_executor_job(scanner.update)
    if not success:
        raise PlatformNotReady("Unable to connect to Tomato router")

    tracked: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add new entities for newly discovered devices."""
        new_entities: list[TomatoDeviceEntity] = []
        for mac in scanner.devices:
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(TomatoDeviceEntity(scanner, mac))
        if new_entities:
            async_add_entities(new_entities)

    async def _async_update(_now: Any = None) -> None:
        """Periodically update device data."""
        await hass.async_add_executor_job(scanner.update)
        _async_add_new_entities()
        async_dispatcher_send(hass, SIGNAL_TOMATO_UPDATE)

    _async_add_new_entities()
    async_track_time_interval(hass, _async_update, SCAN_INTERVAL)


class TomatoData:
    """Handle communication with the Tomato router."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the data handler."""
        host: str = config[CONF_HOST]
        http_id: str = config[CONF_HTTP_ID]
        port: int | None = config.get(CONF_PORT)
        username: str = config[CONF_USERNAME]
        password: str = config[CONF_PASSWORD]
        self._ssl: bool = config[CONF_SSL]
        self._verify_ssl: bool | str = config[CONF_VERIFY_SSL]

        if port is None:
            port = 443 if self._ssl else 80

        protocol = "https" if self._ssl else "http"
        self._req = requests.Request(
            "POST",
            f"{protocol}://{host}:{port}/update.cgi",
            data={"_http_id": http_id, "exec": "devlist"},
            auth=requests.auth.HTTPBasicAuth(username, password),
        ).prepare()

        self._parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")
        self.connected_macs: set[str] = set()
        self.devices: dict[str, dict[str, str | None]] = {}

    def update(self) -> bool:
        """Fetch data from the Tomato router.

        Return boolean if scanning successful.
        """
        _LOGGER.debug("Scanning")

        try:
            if self._ssl:
                response = requests.Session().send(
                    self._req, timeout=60, verify=self._verify_ssl
                )
            else:
                response = requests.Session().send(self._req, timeout=60)

            if response.status_code == HTTPStatus.OK:
                wldev: list[list[Any]] = []
                dhcpd_lease: list[list[Any]] = []

                for param, value in self._parse_api_pattern.findall(response.text):
                    if param == "wldev":
                        wldev = json.loads(value.replace("'", '"'))
                    elif param == "dhcpd_lease":
                        dhcpd_lease = json.loads(value.replace("'", '"'))

                self.connected_macs = {item[1] for item in wldev}

                self.devices = {}
                for lease in dhcpd_lease:
                    mac: str = lease[2]
                    self.devices[mac] = {
                        "hostname": lease[0] or None,
                        "ip": lease[1] or None,
                    }

                return True

            if response.status_code == HTTPStatus.UNAUTHORIZED:
                _LOGGER.exception(
                    "Failed to authenticate, please check your username and password"
                )
                return False

        except requests.exceptions.ConnectionError:
            _LOGGER.exception(
                "Failed to connect to the router or invalid http_id supplied"
            )
            return False

        except requests.exceptions.Timeout:
            _LOGGER.exception("Connection to the router timed out")
            return False

        except ValueError:
            _LOGGER.exception("Failed to parse response from router")
            return False

        return False


class TomatoDeviceEntity(ScannerEntity):
    """Representation of a device connected to a Tomato router."""

    _attr_should_poll = False

    def __init__(self, scanner: TomatoData, mac: str) -> None:
        """Initialize the entity."""
        self._scanner = scanner
        self._mac = mac
        device = scanner.devices.get(mac, {})
        self._attr_name: str | None = device.get("hostname") or mac

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._mac in self._scanner.connected_macs

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        if device := self._scanner.devices.get(self._mac):
            return device.get("hostname")
        return None

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        if device := self._scanner.devices.get(self._mac):
            return device.get("ip")
        return None

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TOMATO_UPDATE,
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        """Handle updated data from the scanner."""
        self.async_write_ha_state()
