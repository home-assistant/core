"""Support for AVM FRITZ!Box classes."""
from __future__ import annotations

from collections.abc import Callable, ValuesView
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
import logging
from types import MappingProxyType
from typing import Any, TypedDict, cast

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzConnectionException,
    FritzSecurityError,
    FritzServiceError,
)
from fritzconnection.lib.fritzhosts import FritzHosts
from fritzconnection.lib.fritzstatus import FritzStatus
from fritzconnection.lib.fritzwlan import DEFAULT_PASSWORD_LENGTH, FritzGuestWLAN

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.components.switch import DOMAIN as DEVICE_SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    update_coordinator,
)
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import (
    CONF_OLD_DISCOVERY,
    DEFAULT_CONF_OLD_DISCOVERY,
    DEFAULT_DEVICE_NAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    FRITZ_EXCEPTIONS,
    SERVICE_CLEANUP,
    SERVICE_REBOOT,
    SERVICE_RECONNECT,
    SERVICE_SET_GUEST_WIFI_PW,
    MeshRoles,
)

_LOGGER = logging.getLogger(__name__)


def _is_tracked(mac: str, current_devices: ValuesView) -> bool:
    """Check if device is already tracked."""
    for tracked in current_devices:
        if mac in tracked:
            return True
    return False


def device_filter_out_from_trackers(
    mac: str,
    device: FritzDevice,
    current_devices: ValuesView,
) -> bool:
    """Check if device should be filtered out from trackers."""
    reason: str | None = None
    if device.ip_address == "":
        reason = "Missing IP"
    elif _is_tracked(mac, current_devices):
        reason = "Already tracked"

    if reason:
        _LOGGER.debug(
            "Skip adding device %s [%s], reason: %s", device.hostname, mac, reason
        )
    return bool(reason)


def _cleanup_entity_filter(device: er.RegistryEntry) -> bool:
    """Filter only relevant entities."""
    return device.domain == DEVICE_TRACKER_DOMAIN or (
        device.domain == DEVICE_SWITCH_DOMAIN and "_internet_access" in device.entity_id
    )


def _ha_is_stopping(activity: str) -> None:
    """Inform that HA is stopping."""
    _LOGGER.info("Cannot execute %s: HomeAssistant is shutting down", activity)


class ClassSetupMissing(Exception):
    """Raised when a Class func is called before setup."""

    def __init__(self) -> None:
        """Init custom exception."""
        super().__init__("Function called before Class setup")


@dataclass
class Device:
    """FRITZ!Box device class."""

    connected: bool
    connected_to: str
    connection_type: str
    ip_address: str
    name: str
    ssid: str | None
    wan_access: bool | None = None


class Interface(TypedDict):
    """Interface details."""

    device: str
    mac: str
    op_mode: str
    ssid: str | None
    type: str


class HostInfo(TypedDict):
    """FRITZ!Box host info class."""

    mac: str
    name: str
    ip: str
    status: bool


class FritzBoxTools(update_coordinator.DataUpdateCoordinator):
    """FritzBoxTools class."""

    def __init__(
        self,
        hass: HomeAssistant,
        password: str,
        username: str = DEFAULT_USERNAME,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        """Initialize FritzboxTools class."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=30),
        )

        self._devices: dict[str, FritzDevice] = {}
        self._options: MappingProxyType[str, Any] | None = None
        self._unique_id: str | None = None
        self.connection: FritzConnection = None
        self.fritz_guest_wifi: FritzGuestWLAN = None
        self.fritz_hosts: FritzHosts = None
        self.fritz_status: FritzStatus = None
        self.hass = hass
        self.host = host
        self.mesh_role = MeshRoles.NONE
        self.device_conn_type: str | None = None
        self.device_is_router: bool = False
        self.password = password
        self.port = port
        self.username = username
        self._model: str | None = None
        self._current_firmware: str | None = None
        self._latest_firmware: str | None = None
        self._update_available: bool = False
        self._release_url: str | None = None

    async def async_setup(
        self, options: MappingProxyType[str, Any] | None = None
    ) -> None:
        """Wrap up FritzboxTools class setup."""
        self._options = options
        await self.hass.async_add_executor_job(self.setup)

    def setup(self) -> None:
        """Set up FritzboxTools class."""
        self.connection = FritzConnection(
            address=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            timeout=60.0,
            pool_maxsize=30,
        )

        if not self.connection:
            _LOGGER.error("Unable to establish a connection with %s", self.host)
            return

        _LOGGER.debug(
            "detected services on %s %s",
            self.host,
            list(self.connection.services.keys()),
        )

        self.fritz_hosts = FritzHosts(fc=self.connection)
        self.fritz_guest_wifi = FritzGuestWLAN(fc=self.connection)
        self.fritz_status = FritzStatus(fc=self.connection)
        info = self.fritz_status.get_device_info()

        _LOGGER.debug(
            "gathered device info of %s %s",
            self.host,
            {
                **vars(info),
                "NewDeviceLog": "***omitted***",
                "NewSerialNumber": "***omitted***",
            },
        )

        if not self._unique_id:
            self._unique_id = info.serial_number

        self._model = info.model_name
        self._current_firmware = info.software_version

        (
            self._update_available,
            self._latest_firmware,
            self._release_url,
        ) = self._update_device_info()

        if self.fritz_status.has_wan_support:
            self.device_conn_type = (
                self.fritz_status.get_default_connection_service().connection_service
            )
            self.device_is_router = self.fritz_status.has_wan_enabled

    async def _async_update_data(self) -> None:
        """Update FritzboxTools data."""
        try:
            await self.async_scan_devices()
        except FRITZ_EXCEPTIONS as ex:
            raise update_coordinator.UpdateFailed(ex) from ex

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        if not self._unique_id:
            raise ClassSetupMissing()
        return self._unique_id

    @property
    def model(self) -> str:
        """Return device model."""
        if not self._model:
            raise ClassSetupMissing()
        return self._model

    @property
    def current_firmware(self) -> str:
        """Return current SW version."""
        if not self._current_firmware:
            raise ClassSetupMissing()
        return self._current_firmware

    @property
    def latest_firmware(self) -> str | None:
        """Return latest SW version."""
        return self._latest_firmware

    @property
    def update_available(self) -> bool:
        """Return if new SW version is available."""
        return self._update_available

    @property
    def release_url(self) -> str | None:
        """Return the info URL for latest firmware."""
        return self._release_url

    @property
    def mac(self) -> str:
        """Return device Mac address."""
        if not self._unique_id:
            raise ClassSetupMissing()
        return dr.format_mac(self._unique_id)

    @property
    def devices(self) -> dict[str, FritzDevice]:
        """Return devices."""
        return self._devices

    @property
    def signal_device_new(self) -> str:
        """Event specific per FRITZ!Box entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._unique_id}"

    @property
    def signal_device_update(self) -> str:
        """Event specific per FRITZ!Box entry to signal updates in devices."""
        return f"{DOMAIN}-device-update-{self._unique_id}"

    def _update_hosts_info(self) -> list[HostInfo]:
        """Retrieve latest hosts information from the FRITZ!Box."""
        try:
            return self.fritz_hosts.get_hosts_info()  # type: ignore [no-any-return]
        except Exception as ex:  # pylint: disable=[broad-except]
            if not self.hass.is_stopping:
                raise HomeAssistantError("Error refreshing hosts info") from ex
        return []

    def _update_device_info(self) -> tuple[bool, str | None, str | None]:
        """Retrieve latest device information from the FRITZ!Box."""
        info = self.connection.call_action("UserInterface1", "GetInfo")
        version = info.get("NewX_AVM-DE_Version")
        release_url = info.get("NewX_AVM-DE_InfoURL")
        return bool(version), version, release_url

    def _get_wan_access(self, ip_address: str) -> bool | None:
        """Get WAN access rule for given IP address."""
        try:
            return not self.connection.call_action(
                "X_AVM-DE_HostFilter:1",
                "GetWANAccessByIP",
                NewIPv4Address=ip_address,
            ).get("NewDisallow")
        except FRITZ_EXCEPTIONS as ex:
            _LOGGER.debug(
                "could not get WAN access rule for client device with IP '%s', error: %s",
                ip_address,
                ex,
            )
            return None

    async def async_scan_devices(self, now: datetime | None = None) -> None:
        """Wrap up FritzboxTools class scan."""
        await self.hass.async_add_executor_job(self.scan_devices, now)

    def manage_device_info(
        self, dev_info: Device, dev_mac: str, consider_home: bool
    ) -> bool:
        """Update device lists."""
        _LOGGER.debug("Client dev_info: %s", dev_info)

        if dev_mac in self._devices:
            self._devices[dev_mac].update(dev_info, consider_home)
            return False

        device = FritzDevice(dev_mac, dev_info.name)
        device.update(dev_info, consider_home)
        self._devices[dev_mac] = device
        return True

    def send_signal_device_update(self, new_device: bool) -> None:
        """Signal device data updated."""
        dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            dispatcher_send(self.hass, self.signal_device_new)

    def scan_devices(self, now: datetime | None = None) -> None:
        """Scan for new devices and return a list of found device ids."""

        if self.hass.is_stopping:
            _ha_is_stopping("scan devices")
            return

        _LOGGER.debug("Checking host info for FRITZ!Box device %s", self.host)
        (
            self._update_available,
            self._latest_firmware,
            self._release_url,
        ) = self._update_device_info()

        _LOGGER.debug("Checking devices for FRITZ!Box device %s", self.host)
        _default_consider_home = DEFAULT_CONSIDER_HOME.total_seconds()
        if self._options:
            consider_home = self._options.get(
                CONF_CONSIDER_HOME, _default_consider_home
            )
        else:
            consider_home = _default_consider_home

        new_device = False
        hosts = {}
        for host in self._update_hosts_info():
            if not host.get("mac"):
                continue

            hosts[host["mac"]] = Device(
                name=host["name"],
                connected=host["status"],
                connected_to="",
                connection_type="",
                ip_address=host["ip"],
                ssid=None,
                wan_access=None,
            )

        if not self.fritz_status.device_has_mesh_support or (
            self._options
            and self._options.get(CONF_OLD_DISCOVERY, DEFAULT_CONF_OLD_DISCOVERY)
        ):
            _LOGGER.debug(
                "Using old hosts discovery method. (Mesh not supported or user option)"
            )
            self.mesh_role = MeshRoles.NONE
            for mac, info in hosts.items():
                if info.ip_address:
                    info.wan_access = self._get_wan_access(info.ip_address)
                if self.manage_device_info(info, mac, consider_home):
                    new_device = True
            self.send_signal_device_update(new_device)
            return

        try:
            if not (topology := self.fritz_hosts.get_mesh_topology()):
                raise Exception("Mesh supported but empty topology reported")
        except FritzActionError:
            self.mesh_role = MeshRoles.SLAVE
            # Avoid duplicating device trackers
            return

        mesh_intf = {}
        # first get all meshed devices
        for node in topology.get("nodes", []):
            if not node["is_meshed"]:
                continue

            for interf in node["node_interfaces"]:
                int_mac = interf["mac_address"]
                mesh_intf[interf["uid"]] = Interface(
                    device=node["device_name"],
                    mac=int_mac,
                    op_mode=interf.get("op_mode", ""),
                    ssid=interf.get("ssid", ""),
                    type=interf["type"],
                )
                if dr.format_mac(int_mac) == self.mac:
                    self.mesh_role = MeshRoles(node["mesh_role"])

        # second get all client devices
        for node in topology.get("nodes", []):
            if node["is_meshed"]:
                continue

            for interf in node["node_interfaces"]:
                dev_mac = interf["mac_address"]

                if dev_mac not in hosts:
                    continue

                dev_info: Device = hosts[dev_mac]

                if dev_info.ip_address:
                    dev_info.wan_access = self._get_wan_access(dev_info.ip_address)

                for link in interf["node_links"]:
                    intf = mesh_intf.get(link["node_interface_1_uid"])
                    if intf is not None:
                        if intf["op_mode"] == "AP_GUEST":
                            dev_info.wan_access = None

                        dev_info.connected_to = intf["device"]
                        dev_info.connection_type = intf["type"]
                        dev_info.ssid = intf.get("ssid")

                if self.manage_device_info(dev_info, dev_mac, consider_home):
                    new_device = True

        self.send_signal_device_update(new_device)

    async def async_trigger_firmware_update(self) -> bool:
        """Trigger firmware update."""
        results = await self.hass.async_add_executor_job(
            self.connection.call_action, "UserInterface:1", "X_AVM-DE_DoUpdate"
        )
        return cast(bool, results["NewX_AVM-DE_UpdateState"])

    async def async_trigger_reboot(self) -> None:
        """Trigger device reboot."""
        await self.hass.async_add_executor_job(self.connection.reboot)

    async def async_trigger_reconnect(self) -> None:
        """Trigger device reconnect."""
        await self.hass.async_add_executor_job(self.connection.reconnect)

    async def async_trigger_set_guest_password(
        self, password: str | None, length: int
    ) -> None:
        """Trigger service to set a new guest wifi password."""
        await self.hass.async_add_executor_job(
            self.fritz_guest_wifi.set_password, password, length
        )

    async def async_trigger_cleanup(
        self, config_entry: ConfigEntry | None = None
    ) -> None:
        """Trigger device trackers cleanup."""
        device_hosts_list = await self.hass.async_add_executor_job(
            self.fritz_hosts.get_hosts_info
        )
        entity_reg: er.EntityRegistry = er.async_get(self.hass)

        if config_entry is None:
            if self.config_entry is None:
                return
            config_entry = self.config_entry

        ha_entity_reg_list: list[er.RegistryEntry] = er.async_entries_for_config_entry(
            entity_reg, config_entry.entry_id
        )
        entities_removed: bool = False

        device_hosts_macs = set()
        device_hosts_names = set()
        for device in device_hosts_list:
            device_hosts_macs.add(device["mac"])
            device_hosts_names.add(device["name"])

        for entry in ha_entity_reg_list:
            if entry.original_name is None:
                continue
            entry_name = entry.name or entry.original_name
            entry_host = entry_name.split(" ")[0]
            entry_mac = entry.unique_id.split("_")[0]

            if not _cleanup_entity_filter(entry) or (
                entry_mac in device_hosts_macs and entry_host in device_hosts_names
            ):
                _LOGGER.debug(
                    "Skipping entity %s [mac=%s, host=%s]",
                    entry_name,
                    entry_mac,
                    entry_host,
                )
                continue
            _LOGGER.info("Removing entity: %s", entry_name)
            entity_reg.async_remove(entry.entity_id)
            entities_removed = True

        if entities_removed:
            self._async_remove_empty_devices(entity_reg, config_entry)

    @callback
    def _async_remove_empty_devices(
        self, entity_reg: er.EntityRegistry, config_entry: ConfigEntry
    ) -> None:
        """Remove devices with no entities."""

        device_reg = dr.async_get(self.hass)
        device_list = dr.async_entries_for_config_entry(
            device_reg, config_entry.entry_id
        )
        for device_entry in device_list:
            if not er.async_entries_for_device(
                entity_reg,
                device_entry.id,
                include_disabled_entities=True,
            ):
                _LOGGER.info("Removing device: %s", device_entry.name)
                device_reg.async_remove_device(device_entry.id)

    async def service_fritzbox(
        self, service_call: ServiceCall, config_entry: ConfigEntry
    ) -> None:
        """Define FRITZ!Box services."""
        _LOGGER.debug("FRITZ!Box service: %s", service_call.service)

        if not self.connection:
            raise HomeAssistantError("Unable to establish a connection")

        try:
            if service_call.service == SERVICE_REBOOT:
                _LOGGER.warning(
                    'Service "fritz.reboot" is deprecated, please use the corresponding button entity instead'
                )
                await self.async_trigger_reboot()
                return

            if service_call.service == SERVICE_RECONNECT:
                _LOGGER.warning(
                    'Service "fritz.reconnect" is deprecated, please use the corresponding button entity instead'
                )
                await self.async_trigger_reconnect()
                return

            if service_call.service == SERVICE_CLEANUP:
                _LOGGER.warning(
                    'Service "fritz.cleanup" is deprecated, please use the corresponding button entity instead'
                )
                await self.async_trigger_cleanup(config_entry)
                return

            if service_call.service == SERVICE_SET_GUEST_WIFI_PW:
                await self.async_trigger_set_guest_password(
                    service_call.data.get("password"),
                    service_call.data.get("length", DEFAULT_PASSWORD_LENGTH),
                )
                return

        except (FritzServiceError, FritzActionError) as ex:
            raise HomeAssistantError("Service or parameter unknown") from ex
        except FritzConnectionException as ex:
            raise HomeAssistantError("Service not supported") from ex


class AvmWrapper(FritzBoxTools):
    """Setup AVM wrapper for API calls."""

    def _service_call_action(
        self,
        service_name: str,
        service_suffix: str,
        action_name: str,
        **kwargs: Any,
    ) -> dict:
        """Return service details."""

        if self.hass.is_stopping:
            _ha_is_stopping(f"{service_name}/{action_name}")
            return {}

        if f"{service_name}{service_suffix}" not in self.connection.services:
            return {}

        try:
            result: dict = self.connection.call_action(
                f"{service_name}:{service_suffix}",
                action_name,
                **kwargs,
            )
            return result
        except FritzSecurityError:
            _LOGGER.error(
                "Authorization Error: Please check the provided credentials and verify that you can log into the web interface",
                exc_info=True,
            )
        except FRITZ_EXCEPTIONS:
            _LOGGER.error(
                "Service/Action Error: cannot execute service %s with action %s",
                service_name,
                action_name,
                exc_info=True,
            )
        except FritzConnectionException:
            _LOGGER.error(
                "Connection Error: Please check the device is properly configured for remote login",
                exc_info=True,
            )
        return {}

    async def async_get_upnp_configuration(self) -> dict[str, Any]:
        """Call X_AVM-DE_UPnP service."""

        return await self.hass.async_add_executor_job(self.get_upnp_configuration)

    async def async_get_wan_link_properties(self) -> dict[str, Any]:
        """Call WANCommonInterfaceConfig service."""

        return await self.hass.async_add_executor_job(
            partial(self.get_wan_link_properties)
        )

    async def async_get_connection_info(self) -> ConnectionInfo:
        """Return ConnectionInfo data."""

        link_properties = await self.async_get_wan_link_properties()
        connection_info = ConnectionInfo(
            connection=link_properties.get("NewWANAccessType", "").lower(),
            mesh_role=self.mesh_role,
            wan_enabled=self.device_is_router,
        )
        _LOGGER.debug(
            "ConnectionInfo for FritzBox %s: %s",
            self.host,
            connection_info,
        )
        return connection_info

    async def async_get_port_mapping(self, con_type: str, index: int) -> dict[str, Any]:
        """Call GetGenericPortMappingEntry action."""

        return await self.hass.async_add_executor_job(
            partial(self.get_port_mapping, con_type, index)
        )

    async def async_get_wlan_configuration(self, index: int) -> dict[str, Any]:
        """Call WLANConfiguration service."""

        return await self.hass.async_add_executor_job(
            partial(self.get_wlan_configuration, index)
        )

    async def async_get_ontel_deflections(self) -> dict[str, Any]:
        """Call GetDeflections action from X_AVM-DE_OnTel service."""

        return await self.hass.async_add_executor_job(
            partial(self.get_ontel_deflections)
        )

    async def async_set_wlan_configuration(
        self, index: int, turn_on: bool
    ) -> dict[str, Any]:
        """Call SetEnable action from WLANConfiguration service."""

        return await self.hass.async_add_executor_job(
            partial(self.set_wlan_configuration, index, turn_on)
        )

    async def async_set_deflection_enable(
        self, index: int, turn_on: bool
    ) -> dict[str, Any]:
        """Call SetDeflectionEnable service."""

        return await self.hass.async_add_executor_job(
            partial(self.set_deflection_enable, index, turn_on)
        )

    async def async_add_port_mapping(
        self, con_type: str, port_mapping: Any
    ) -> dict[str, Any]:
        """Call AddPortMapping service."""

        return await self.hass.async_add_executor_job(
            partial(
                self.add_port_mapping,
                con_type,
                port_mapping,
            )
        )

    async def async_set_allow_wan_access(
        self, ip_address: str, turn_on: bool
    ) -> dict[str, Any]:
        """Call X_AVM-DE_HostFilter service."""

        return await self.hass.async_add_executor_job(
            partial(self.set_allow_wan_access, ip_address, turn_on)
        )

    def get_upnp_configuration(self) -> dict[str, Any]:
        """Call X_AVM-DE_UPnP service."""

        return self._service_call_action("X_AVM-DE_UPnP", "1", "GetInfo")

    def get_ontel_num_deflections(self) -> dict[str, Any]:
        """Call GetNumberOfDeflections action from X_AVM-DE_OnTel service."""

        return self._service_call_action(
            "X_AVM-DE_OnTel", "1", "GetNumberOfDeflections"
        )

    def get_ontel_deflections(self) -> dict[str, Any]:
        """Call GetDeflections action from X_AVM-DE_OnTel service."""

        return self._service_call_action("X_AVM-DE_OnTel", "1", "GetDeflections")

    def get_default_connection(self) -> dict[str, Any]:
        """Call Layer3Forwarding service."""

        return self._service_call_action(
            "Layer3Forwarding", "1", "GetDefaultConnectionService"
        )

    def get_num_port_mapping(self, con_type: str) -> dict[str, Any]:
        """Call GetPortMappingNumberOfEntries action."""

        return self._service_call_action(con_type, "1", "GetPortMappingNumberOfEntries")

    def get_port_mapping(self, con_type: str, index: int) -> dict[str, Any]:
        """Call GetGenericPortMappingEntry action."""

        return self._service_call_action(
            con_type, "1", "GetGenericPortMappingEntry", NewPortMappingIndex=index
        )

    def get_wlan_configuration(self, index: int) -> dict[str, Any]:
        """Call WLANConfiguration service."""

        return self._service_call_action("WLANConfiguration", str(index), "GetInfo")

    def get_wan_link_properties(self) -> dict[str, Any]:
        """Call WANCommonInterfaceConfig service."""

        return self._service_call_action(
            "WANCommonInterfaceConfig", "1", "GetCommonLinkProperties"
        )

    def set_wlan_configuration(self, index: int, turn_on: bool) -> dict[str, Any]:
        """Call SetEnable action from WLANConfiguration service."""

        return self._service_call_action(
            "WLANConfiguration",
            str(index),
            "SetEnable",
            NewEnable="1" if turn_on else "0",
        )

    def set_deflection_enable(self, index: int, turn_on: bool) -> dict[str, Any]:
        """Call SetDeflectionEnable service."""

        return self._service_call_action(
            "X_AVM-DE_OnTel",
            "1",
            "SetDeflectionEnable",
            NewDeflectionId=index,
            NewEnable="1" if turn_on else "0",
        )

    def add_port_mapping(self, con_type: str, port_mapping: Any) -> dict[str, Any]:
        """Call AddPortMapping service."""

        return self._service_call_action(
            con_type, "1", "AddPortMapping", **port_mapping
        )

    def set_allow_wan_access(self, ip_address: str, turn_on: bool) -> dict[str, Any]:
        """Call X_AVM-DE_HostFilter service."""

        return self._service_call_action(
            "X_AVM-DE_HostFilter",
            "1",
            "DisallowWANAccessByIP",
            NewIPv4Address=ip_address,
            NewDisallow="0" if turn_on else "1",
        )


@dataclass
class FritzData:
    """Storage class for platform global data."""

    tracked: dict = field(default_factory=dict)
    profile_switches: dict = field(default_factory=dict)


class FritzDeviceBase(update_coordinator.CoordinatorEntity[AvmWrapper]):
    """Entity base class for a device connected to a FRITZ!Box device."""

    def __init__(self, avm_wrapper: AvmWrapper, device: FritzDevice) -> None:
        """Initialize a FRITZ!Box device."""
        super().__init__(avm_wrapper)
        self._avm_wrapper = avm_wrapper
        self._mac: str = device.mac_address
        self._name: str = device.hostname or DEFAULT_DEVICE_NAME

    @property
    def name(self) -> str:
        """Return device name."""
        return self._name

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        if self._mac:
            return self._avm_wrapper.devices[self._mac].ip_address
        return None

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        if self._mac:
            return self._avm_wrapper.devices[self._mac].hostname
        return None

    async def async_process_update(self) -> None:
        """Update device."""
        raise NotImplementedError()

    async def async_on_demand_update(self) -> None:
        """Update state."""
        await self.async_process_update()
        self.async_write_ha_state()


class FritzDevice:
    """Representation of a device connected to the FRITZ!Box."""

    def __init__(self, mac: str, name: str) -> None:
        """Initialize device info."""
        self._connected = False
        self._connected_to: str | None = None
        self._connection_type: str | None = None
        self._ip_address: str | None = None
        self._last_activity: datetime | None = None
        self._mac = mac
        self._name = name
        self._ssid: str | None = None
        self._wan_access: bool | None = False

    def update(self, dev_info: Device, consider_home: float) -> None:
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

        self._connected_to = dev_info.connected_to
        self._connection_type = dev_info.connection_type
        self._ip_address = dev_info.ip_address
        self._ssid = dev_info.ssid
        self._wan_access = dev_info.wan_access

    @property
    def connected_to(self) -> str | None:
        """Return connected status."""
        return self._connected_to

    @property
    def connection_type(self) -> str | None:
        """Return connected status."""
        return self._connection_type

    @property
    def is_connected(self) -> bool:
        """Return connected status."""
        return self._connected

    @property
    def mac_address(self) -> str:
        """Get MAC address."""
        return self._mac

    @property
    def hostname(self) -> str:
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
    def ssid(self) -> str | None:
        """Return device connected SSID."""
        return self._ssid

    @property
    def wan_access(self) -> bool | None:
        """Return device wan access."""
        return self._wan_access


class SwitchInfo(TypedDict):
    """FRITZ!Box switch info class."""

    description: str
    friendly_name: str
    icon: str
    type: str
    callback_update: Callable
    callback_switch: Callable


class FritzBoxBaseEntity:
    """Fritz host entity base class."""

    def __init__(self, avm_wrapper: AvmWrapper, device_name: str) -> None:
        """Init device info class."""
        self._avm_wrapper = avm_wrapper
        self._device_name = device_name

    @property
    def mac_address(self) -> str:
        """Return the mac address of the main device."""
        return self._avm_wrapper.mac

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            configuration_url=f"http://{self._avm_wrapper.host}",
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac_address)},
            identifiers={(DOMAIN, self._avm_wrapper.unique_id)},
            manufacturer="AVM",
            model=self._avm_wrapper.model,
            name=self._device_name,
            sw_version=self._avm_wrapper.current_firmware,
        )


@dataclass
class ConnectionInfo:
    """Fritz sensor connection information class."""

    connection: str
    mesh_role: MeshRoles
    wan_enabled: bool
