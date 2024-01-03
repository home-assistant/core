"""The upc_connect component."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from connect_box import ConnectBox
from connect_box.exceptions import ConnectBoxError, ConnectBoxLoginError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import DOMAIN, PLATFORMS, TRACKER_SCAN_INTERVAL, UPC_CONNECT_TRACKED_DEVICES

_LOGGER = logging.getLogger(__name__)

# Device(
#     mac='30:24:32:FE:33:14',
#     hostname='homeassistant',
#     ip=IPv4Address('192.168.0.52'),
#     interface='UPC9468090',
#     speed='526',
#     interface_id='19',
#     method='1',
#     lease_time=datetime.datetime(1900, 1, 1, 0, 0)
# )


@dataclass
class UpcConnectDevice:
    """Class for keeping track of an upc connect tracked device."""

    mac_address: str
    hostname: str
    name: str
    ip_address: str
    last_update: datetime
    first_offline: datetime | None


class UpcConnectTrackedDevices:
    """Storage class for all upc connect trackers."""

    def __init__(self) -> None:
        """Initialize the data."""
        self.tracked: dict[str, UpcConnectDevice] = {}
        self.ipv4_last_mac: dict[str, str] = {}
        self.config_entry_owner: dict[str, str] = {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UPC Connect from a config entry."""
    _LOGGER.debug("Set up UPC Connect from a config entry")

    domain_data = hass.data.setdefault(DOMAIN, {})
    devices = domain_data.setdefault(
        UPC_CONNECT_TRACKED_DEVICES, UpcConnectTrackedDevices()
    )
    entry.async_on_unload(entry.add_update_listener(update_listener))
    scanner = domain_data[entry.entry_id] = UpcConnectDeviceScanner(
        hass, entry, devices
    )
    await scanner.async_setup()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug("Handle options update: entry_id=%s", entry.entry_id)

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload UPC Connect config entry."""
    _LOGGER.debug("Unload UPC Connect config entry: entry_id=%s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _async_untrack_devices(hass, entry)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@callback
def _async_untrack_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove tracking for devices owned by this config entry."""
    _LOGGER.debug(
        "Remove tracking for devices owned by this config entry: entry_id=%s",
        entry.entry_id,
    )

    devices = hass.data[DOMAIN][UPC_CONNECT_TRACKED_DEVICES]
    remove_mac_addresses = [
        mac_address
        for mac_address, entry_id in devices.config_entry_owner.items()
        if entry_id == entry.entry_id
    ]
    for mac_address in remove_mac_addresses:
        if device := devices.tracked.pop(mac_address, None):
            devices.ipv4_last_mac.pop(device.ip_address, None)
        del devices.config_entry_owner[mac_address]


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Handle options update: entry_id=%s", entry.entry_id)

    await hass.config_entries.async_reload(entry.entry_id)


def signal_device_update(mac_address) -> str:
    """Signal specific per upc connect tracker entry to signal updates in device."""
    return f"{DOMAIN}-device-update-{mac_address}"


class UpcConnectDeviceScanner:
    """Scanner for devices using upc connect."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, devices: UpcConnectTrackedDevices
    ) -> None:
        """Initialize the scanner."""
        self.devices = devices
        self._hass = hass
        self._entry = entry

        self._stopping = False
        self._connect_box = None

        self._entry_id = entry.entry_id
        self._host = None
        self._password = None

        self._known_mac_addresses: dict[str, str] = {}
        self._finished_first_scan = False

    async def async_setup(self):
        """Set up the tracker."""
        config = self._entry.options
        self._host = config[CONF_HOST]
        self._password = config[CONF_PASSWORD]

        if self._hass.state == CoreState.running:
            await self._async_start_scanner()
            return

        registry = er.async_get(self._hass)
        self._known_mac_addresses = {
            entry.unique_id: entry.original_name
            for entry in registry.entities.values()
            if entry.config_entry_id == self._entry_id
        }

    @property
    def signal_device_new(self) -> str:
        """Signal specific per nmap tracker entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._entry_id}"

    @property
    def signal_device_missing(self) -> str:
        """Signal specific per nmap tracker entry to signal a missing device."""
        return f"{DOMAIN}-device-missing-{self._entry_id}"

    @callback
    def _async_stop(self):
        """Stop the scanner."""
        self._stopping = True

    async def _async_start_scanner(self, *_):
        """Start the scanner."""
        self._entry.async_on_unload(self._async_stop)
        self._entry.async_on_unload(
            async_track_time_interval(
                self._hass,
                self._async_scan_devices,
                timedelta(seconds=TRACKER_SCAN_INTERVAL),
            )
        )

        self._hass.async_create_task(self._async_scan_devices())

    async def _async_scan_devices(self, *_):
        try:
            await self._async_connect_box_scan()
        except ConnectBoxLoginError:
            _LOGGER.error("ConnectBox login data error!")
        except ConnectBoxError as ex:
            _LOGGER.error("ConnectBox scanning failed: %s", ex)

        # if not self._finished_first_scan:
        #     self._finished_first_scan = True
        #     await self._async_mark_missing_devices_as_not_home()

    async def _async_connect_box_scan(self):
        _LOGGER.debug("Start scanning devices")
        if not self._connect_box:
            session = async_get_clientsession(self._hass)
            self._connect_box = ConnectBox(
                session, password=self._password, host=self._host
            )
        await self._connect_box.async_get_devices()
        result = self._connect_box.devices
        if self._stopping:
            return
        # result = [d for d in result if "Kamils-MBP" in str(d)]
        _LOGGER.debug("Detected %s devices", len(result))

        devices = self.devices
        entry_id = self._entry_id
        now = dt_util.now()
        for scanned_device in result:
            mac = scanned_device.mac

            formatted_mac = format_mac(mac)
            if (
                devices.config_entry_owner.setdefault(formatted_mac, entry_id)
                != entry_id
            ):
                expected_entry_id = devices.config_entry_owner[formatted_mac]
                _LOGGER.debug(
                    "Wrong entity owner: %s != %s", expected_entry_id, entry_id
                )
                continue
            ip_address = str(scanned_device.ip)
            hostname = scanned_device.hostname or ip_address
            name = hostname or f"UPC Connect Tracker {formatted_mac}"

            upc_connect_device = UpcConnectDevice(
                mac_address=formatted_mac,
                hostname=hostname,
                name=name,
                ip_address=ip_address,
                last_update=now,
                first_offline=None,
            )
            new = formatted_mac not in devices.tracked
            devices.tracked[formatted_mac] = upc_connect_device
            devices.ipv4_last_mac[ip_address] = formatted_mac
            if new:
                _LOGGER.info("Found new device: %s", upc_connect_device)
                async_dispatcher_send(self._hass, self.signal_device_new, formatted_mac)
            else:
                _LOGGER.info("Found already known device: %s", upc_connect_device)
                async_dispatcher_send(
                    self._hass, signal_device_update(formatted_mac), True
                )

    async def _async_mark_missing_devices_as_not_home(self):
        # After all config entries have finished their first
        # scan we mark devices that were not found as not_home
        # from unavailable
        _LOGGER.debug("Marking missing devices as not home")
        now = dt_util.now()
        for mac_address, original_name in self._known_mac_addresses.items():
            if mac_address in self.devices.tracked:
                continue
            self.devices.config_entry_owner[mac_address] = self._entry_id
            self.devices.tracked[mac_address] = UpcConnectDevice(
                mac_address=mac_address,
                hostname=None,
                name=original_name,
                ip_address=None,
                last_update=now,
                first_offline=now,
            )
