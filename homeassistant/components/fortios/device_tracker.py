"""Support to use FortiOS device like FortiGate as device tracker."""

import logging
from typing import override

from awesomeversion import AwesomeVersion
from fortiosapi import FortiOSAPI
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    ScannerEntity,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)
DEFAULT_VERIFY_SSL = False

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up FortiOS device tracker from YAML configuration."""
    host = config[CONF_HOST]
    verify_ssl = config[CONF_VERIFY_SSL]
    token = config[CONF_TOKEN]

    fgt = FortiOSAPI()

    try:
        fgt.tokenlogin(host, token, verify_ssl, None, 12, "root")
    except ConnectionError as ex:
        _LOGGER.error("ConnectionError to FortiOS API: %s", ex)
        return
    except Exception as ex:  # noqa: BLE001
        _LOGGER.error("Failed to login to FortiOS API: %s", ex)
        return

    status_json = fgt.monitor("system/status", "")

    current_version = AwesomeVersion(status_json["version"])
    minimum_version = AwesomeVersion("6.4.3")
    if current_version < minimum_version:
        _LOGGER.error(
            "Unsupported FortiOS version: %s. Version %s and newer are supported",
            current_version,
            minimum_version,
        )
        return

    scanner = FortiOSDataScanner(fgt, async_add_entities)
    scanner.update()


class FortiOSDataScanner:
    """Class to query FortiOS unit and create entities."""

    def __init__(
        self, fgt: FortiOSAPI, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Initialize the scanner."""
        self._fgt = fgt
        self.async_add_entities = async_add_entities
        self.devices: dict[str, FortiOSDeviceEntity] = {}

    def update(self) -> None:
        """Update clients from device and manage entities."""
        clients_json = self._fgt.monitor(
            "user/device/query",
            "",
            parameters={"filter": "format=master_mac|hostname|is_online"},
        )

        if not clients_json or "results" not in clients_json:
            return

        new_entities: list[FortiOSDeviceEntity] = []

        try:
            for client in clients_json["results"]:
                if "master_mac" not in client:
                    continue

                mac = client["master_mac"].upper()
                is_online = client.get("is_online", False)
                hostname = client.get("hostname")

                if mac not in self.devices:
                    entity = FortiOSDeviceEntity(mac, hostname, is_online, self)
                    self.devices[mac] = entity
                    new_entities.append(entity)
                else:
                    self.devices[mac].update_data(hostname, is_online)

            if new_entities:
                self.async_add_entities(new_entities)

        except KeyError as kex:
            _LOGGER.error("Key not found in clients: %s", kex)


class FortiOSDeviceEntity(ScannerEntity):
    """Representation of a FortiOS tracked device."""

    def __init__(
        self,
        mac: str,
        hostname: str | None,
        is_connected: bool,
        scanner: FortiOSDataScanner,
    ) -> None:
        """Initialize device tracker entity."""
        self._mac = mac
        self._hostname = hostname
        self._is_connected = is_connected
        self._scanner = scanner

    @property
    @override
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        return self._hostname

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._is_connected

    def update_data(self, hostname: str | None, is_connected: bool) -> None:
        """Update state data for the device."""
        self._hostname = hostname
        self._is_connected = is_connected

    @override
    def update(self) -> None:
        """Update state of entity."""
        self._scanner.update()
