"""Device tracker support for OPNsense routers."""

from typing import Any, NewType

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException

from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_API_SECRET,
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
)
from .types import APIData

DeviceDetails = NewType("DeviceDetails", dict[str, Any])
DeviceDetailsByMAC = NewType("DeviceDetailsByMAC", dict[str, DeviceDetails])


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> DeviceScanner | None:
    """Configure the OPNsense device_tracker."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    scanner = OPNsenseDeviceScanner(
        config_entry.runtime_data[CONF_INTERFACE_CLIENT],
        config_entry.runtime_data.get(CONF_TRACKER_INTERFACES, []),
    )
    return scanner if scanner.success_init else None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for OPNsense integration."""
    api_data: APIData = {
        "api_key": config_entry.data[CONF_API_KEY],
        "api_secret": config_entry.data[CONF_API_SECRET],
        "base_url": config_entry.data[CONF_URL],
        "verify_cert": config_entry.data[CONF_VERIFY_SSL],
    }

    tracker_interfaces = config_entry.data.get(CONF_TRACKER_INTERFACES)

    interfaces_client = diagnostics.InterfaceClient(**api_data)

    # Test connection
    try:
        await hass.async_add_executor_job(interfaces_client.get_arp)
    except APIException as err:
        raise ConfigEntryNotReady(f"Unable to connect to OPNsense API: {err}") from err

    config_entry.runtime_data = {
        CONF_INTERFACE_CLIENT: interfaces_client,
        CONF_TRACKER_INTERFACES: tracker_interfaces,
    }


class OPNsenseDeviceScanner(DeviceScanner):
    """This class queries a router running OPNsense."""

    def __init__(
        self, client: diagnostics.InterfaceClient, interfaces: list[str]
    ) -> None:
        """Initialize the scanner."""
        self.last_results: dict[str, Any] = {}
        self.client = client
        self.interfaces = interfaces
        self.success_init = self.update_info()

    def _get_mac_addrs(self, devices: list[DeviceDetails]) -> DeviceDetailsByMAC | dict:
        """Create dict with mac address keys from list of devices."""
        out_devices = {}
        for device in devices:
            if not self.interfaces or device["intf_description"] in self.interfaces:
                out_devices[device["mac"]] = device
        return out_devices

    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self.update_info()
        return list(self.last_results)

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        if device not in self.last_results:
            return None
        return self.last_results[device].get("hostname") or None

    def update_info(self) -> bool:
        """Ensure the information from the OPNsense router is up to date.

        Return boolean if scanning successful.
        """
        devices = self.client.get_arp()
        self.last_results = self._get_mac_addrs(devices)
        return True

    def get_extra_attributes(self, device: str) -> dict[Any, Any]:
        """Return the extra attrs of the given device."""
        if device not in self.last_results:
            return {}
        mfg = self.last_results[device].get("manufacturer")
        if not mfg:
            return {}
        return {"manufacturer": mfg}
