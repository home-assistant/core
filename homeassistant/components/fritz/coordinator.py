"""Support for AVM FRITZ!Box classes."""

from __future__ import annotations

from collections.abc import Callable, ValuesView
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
import logging
import re
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
import xmltodict

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_OLD_DISCOVERY,
    DEFAULT_CONF_OLD_DISCOVERY,
    DEFAULT_HOST,
    DEFAULT_SSL,
    DEFAULT_USERNAME,
    DOMAIN,
    FRITZ_EXCEPTIONS,
    SERVICE_SET_GUEST_WIFI_PW,
    MeshRoles,
)

_LOGGER = logging.getLogger(__name__)


def _is_tracked(mac: str, current_devices: ValuesView) -> bool:
    """Check if device is already tracked."""
    return any(mac in tracked for tracked in current_devices)


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


HostAttributes = TypedDict(
    "HostAttributes",
    {
        "Index": int,
        "IPAddress": str,
        "MACAddress": str,
        "Active": bool,
        "HostName": str,
        "InterfaceType": str,
        "X_AVM-DE_Port": int,
        "X_AVM-DE_Speed": int,
        "X_AVM-DE_UpdateAvailable": bool,
        "X_AVM-DE_UpdateSuccessful": str,
        "X_AVM-DE_InfoURL": str | None,
        "X_AVM-DE_MACAddressList": str | None,
        "X_AVM-DE_Model": str | None,
        "X_AVM-DE_URL": str | None,
        "X_AVM-DE_Guest": bool,
        "X_AVM-DE_RequestClient": str,
        "X_AVM-DE_VPN": bool,
        "X_AVM-DE_WANAccess": str,
        "X_AVM-DE_Disallow": bool,
        "X_AVM-DE_IsMeshable": str,
        "X_AVM-DE_Priority": str,
        "X_AVM-DE_FriendlyName": str,
        "X_AVM-DE_FriendlyNameIsWriteable": str,
    },
)


class HostInfo(TypedDict):
    """FRITZ!Box host info class."""

    mac: str
    name: str
    ip: str
    status: bool


class UpdateCoordinatorDataType(TypedDict):
    """Update coordinator data type."""

    call_deflections: dict[int, dict]
    entity_states: dict[str, StateType | bool]


class FritzBoxTools(DataUpdateCoordinator[UpdateCoordinatorDataType]):
    """FritzBoxTools class."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        password: str,
        port: int,
        username: str = DEFAULT_USERNAME,
        host: str = DEFAULT_HOST,
        use_tls: bool = DEFAULT_SSL,
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
        self.use_tls = use_tls
        self.has_call_deflections: bool = False
        self._model: str | None = None
        self._current_firmware: str | None = None
        self._latest_firmware: str | None = None
        self._update_available: bool = False
        self._release_url: str | None = None
        self._entity_update_functions: dict[
            str, Callable[[FritzStatus, StateType], Any]
        ] = {}

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
            use_tls=self.use_tls,
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
        if (
            version_normalized := re.search(r"^\d+\.[0]?(.*)", info.software_version)
        ) is not None:
            self._current_firmware = version_normalized.group(1)
        else:
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

        self.has_call_deflections = "X_AVM-DE_OnTel1" in self.connection.services

    async def async_register_entity_updates(
        self, key: str, update_fn: Callable[[FritzStatus, StateType], Any]
    ) -> Callable[[], None]:
        """Register an entity to be updated by coordinator."""

        def unregister_entity_updates() -> None:
            """Unregister an entity to be updated by coordinator."""
            if key in self._entity_update_functions:
                _LOGGER.debug("unregister entity %s from updates", key)
                self._entity_update_functions.pop(key)

        if key not in self._entity_update_functions:
            _LOGGER.debug("register entity %s for updates", key)
            self._entity_update_functions[key] = update_fn
            if self.fritz_status:
                self.data["entity_states"][
                    key
                ] = await self.hass.async_add_executor_job(
                    update_fn, self.fritz_status, self.data["entity_states"].get(key)
                )
        return unregister_entity_updates

    def _entity_states_update(self) -> dict:
        """Run registered entity update calls."""
        entity_states = {}
        for key in list(self._entity_update_functions):
            if (update_fn := self._entity_update_functions.get(key)) is not None:
                _LOGGER.debug("update entity %s", key)
                entity_states[key] = update_fn(
                    self.fritz_status, self.data["entity_states"].get(key)
                )
        return entity_states

    async def _async_update_data(self) -> UpdateCoordinatorDataType:
        """Update FritzboxTools data."""
        entity_data: UpdateCoordinatorDataType = {
            "call_deflections": {},
            "entity_states": {},
        }
        try:
            await self.async_scan_devices()
            entity_data["entity_states"] = await self.hass.async_add_executor_job(
                self._entity_states_update
            )
            if self.has_call_deflections:
                entity_data[
                    "call_deflections"
                ] = await self.async_update_call_deflections()
        except FRITZ_EXCEPTIONS as ex:
            raise UpdateFailed(ex) from ex

        _LOGGER.debug("enity_data: %s", entity_data)
        return entity_data

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        if not self._unique_id:
            raise ClassSetupMissing
        return self._unique_id

    @property
    def model(self) -> str:
        """Return device model."""
        if not self._model:
            raise ClassSetupMissing
        return self._model

    @property
    def current_firmware(self) -> str:
        """Return current SW version."""
        if not self._current_firmware:
            raise ClassSetupMissing
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
            raise ClassSetupMissing
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

    async def _async_get_wan_access(self, ip_address: str) -> bool | None:
        """Get WAN access rule for given IP address."""
        try:
            wan_access = await self.hass.async_add_executor_job(
                partial(
                    self.connection.call_action,
                    "X_AVM-DE_HostFilter:1",
                    "GetWANAccessByIP",
                    NewIPv4Address=ip_address,
                )
            )
            return not wan_access.get("NewDisallow")
        except FRITZ_EXCEPTIONS as ex:
            _LOGGER.debug(
                (
                    "could not get WAN access rule for client device with IP '%s',"
                    " error: %s"
                ),
                ip_address,
                ex,
            )
            return None

    async def _async_update_hosts_info(self) -> dict[str, Device]:
        """Retrieve latest hosts information from the FRITZ!Box."""
        hosts_attributes: list[HostAttributes] = []
        hosts_info: list[HostInfo] = []
        try:
            try:
                hosts_attributes = await self.hass.async_add_executor_job(
                    self.fritz_hosts.get_hosts_attributes
                )
            except FritzActionError:
                hosts_info = await self.hass.async_add_executor_job(
                    self.fritz_hosts.get_hosts_info
                )
        except Exception as ex:  # noqa: BLE001
            if not self.hass.is_stopping:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="error_refresh_hosts_info",
                ) from ex

        hosts: dict[str, Device] = {}
        if hosts_attributes:
            for attributes in hosts_attributes:
                if not attributes.get("MACAddress"):
                    continue

                if (wan_access := attributes.get("X_AVM-DE_WANAccess")) is not None:
                    wan_access_result = "granted" in wan_access
                else:
                    wan_access_result = None

                hosts[attributes["MACAddress"]] = Device(
                    name=attributes["HostName"],
                    connected=attributes["Active"],
                    connected_to="",
                    connection_type="",
                    ip_address=attributes["IPAddress"],
                    ssid=None,
                    wan_access=wan_access_result,
                )
        else:
            for info in hosts_info:
                if not info.get("mac"):
                    continue

                if info["ip"]:
                    wan_access_result = await self._async_get_wan_access(info["ip"])
                else:
                    wan_access_result = None

                hosts[info["mac"]] = Device(
                    name=info["name"],
                    connected=info["status"],
                    connected_to="",
                    connection_type="",
                    ip_address=info["ip"],
                    ssid=None,
                    wan_access=wan_access_result,
                )
        return hosts

    def _update_device_info(self) -> tuple[bool, str | None, str | None]:
        """Retrieve latest device information from the FRITZ!Box."""
        info = self.connection.call_action("UserInterface1", "GetInfo")
        version = info.get("NewX_AVM-DE_Version")
        release_url = info.get("NewX_AVM-DE_InfoURL")
        return bool(version), version, release_url

    async def _async_update_device_info(self) -> tuple[bool, str | None, str | None]:
        """Retrieve latest device information from the FRITZ!Box."""
        return await self.hass.async_add_executor_job(self._update_device_info)

    async def async_update_call_deflections(
        self,
    ) -> dict[int, dict[str, Any]]:
        """Call GetDeflections action from X_AVM-DE_OnTel service."""
        raw_data = await self.hass.async_add_executor_job(
            partial(self.connection.call_action, "X_AVM-DE_OnTel1", "GetDeflections")
        )
        if not raw_data:
            return {}

        xml_data = xmltodict.parse(raw_data["NewDeflectionList"])
        if xml_data.get("List") and (items := xml_data["List"].get("Item")) is not None:
            if not isinstance(items, list):
                items = [items]
            return {int(item["DeflectionId"]): item for item in items}
        return {}

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

    async def async_send_signal_device_update(self, new_device: bool) -> None:
        """Signal device data updated."""
        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    async def async_scan_devices(self, now: datetime | None = None) -> None:
        """Scan for new devices and return a list of found device ids."""

        if self.hass.is_stopping:
            _ha_is_stopping("scan devices")
            return

        _LOGGER.debug("Checking host info for FRITZ!Box device %s", self.host)
        (
            self._update_available,
            self._latest_firmware,
            self._release_url,
        ) = await self._async_update_device_info()

        _LOGGER.debug("Checking devices for FRITZ!Box device %s", self.host)
        _default_consider_home = DEFAULT_CONSIDER_HOME.total_seconds()
        if self._options:
            consider_home = self._options.get(
                CONF_CONSIDER_HOME, _default_consider_home
            )
        else:
            consider_home = _default_consider_home

        new_device = False
        hosts = await self._async_update_hosts_info()

        if not self.fritz_status.device_has_mesh_support or (
            self._options
            and self._options.get(CONF_OLD_DISCOVERY, DEFAULT_CONF_OLD_DISCOVERY)
        ):
            _LOGGER.debug(
                "Using old hosts discovery method. (Mesh not supported or user option)"
            )
            self.mesh_role = MeshRoles.NONE
            for mac, info in hosts.items():
                if self.manage_device_info(info, mac, consider_home):
                    new_device = True
            await self.async_send_signal_device_update(new_device)
            return

        try:
            if not (
                topology := await self.hass.async_add_executor_job(
                    self.fritz_hosts.get_mesh_topology
                )
            ):
                # pylint: disable-next=broad-exception-raised
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

        await self.async_send_signal_device_update(new_device)

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

    async def async_trigger_cleanup(self) -> None:
        """Trigger device trackers cleanup."""
        device_hosts = await self._async_update_hosts_info()
        entity_reg: er.EntityRegistry = er.async_get(self.hass)
        config_entry = self.config_entry

        entities: list[er.RegistryEntry] = er.async_entries_for_config_entry(
            entity_reg, config_entry.entry_id
        )

        orphan_macs: set[str] = set()
        for entity in entities:
            entry_mac = entity.unique_id.split("_")[0]
            if (
                entity.domain == DEVICE_TRACKER_DOMAIN
                or "_internet_access" in entity.unique_id
            ) and entry_mac not in device_hosts:
                _LOGGER.info("Removing orphan entity entry %s", entity.entity_id)
                orphan_macs.add(entry_mac)
                entity_reg.async_remove(entity.entity_id)

        device_reg = dr.async_get(self.hass)
        orphan_connections = {(CONNECTION_NETWORK_MAC, mac) for mac in orphan_macs}
        for device in dr.async_entries_for_config_entry(
            device_reg, config_entry.entry_id
        ):
            if any(con in device.connections for con in orphan_connections):
                _LOGGER.debug("Removing obsolete device entry %s", device.name)
                device_reg.async_update_device(
                    device.id, remove_config_entry_id=config_entry.entry_id
                )

    async def service_fritzbox(
        self, service_call: ServiceCall, config_entry: ConfigEntry
    ) -> None:
        """Define FRITZ!Box services."""
        _LOGGER.debug("FRITZ!Box service: %s", service_call.service)

        if not self.connection:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unable_to_connect"
            )

        try:
            if service_call.service == SERVICE_SET_GUEST_WIFI_PW:
                await self.async_trigger_set_guest_password(
                    service_call.data.get("password"),
                    service_call.data.get("length", DEFAULT_PASSWORD_LENGTH),
                )
                return

        except (FritzServiceError, FritzActionError) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_parameter_unknown"
            ) from ex
        except FritzConnectionException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_not_supported"
            ) from ex


class AvmWrapper(FritzBoxTools):
    """Setup AVM wrapper for API calls."""

    async def _async_service_call(
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
            result: dict = await self.hass.async_add_executor_job(
                partial(
                    self.connection.call_action,
                    f"{service_name}:{service_suffix}",
                    action_name,
                    **kwargs,
                )
            )
        except FritzSecurityError:
            _LOGGER.exception(
                "Authorization Error: Please check the provided credentials and"
                " verify that you can log into the web interface"
            )
            return {}
        except FRITZ_EXCEPTIONS:
            _LOGGER.exception(
                "Service/Action Error: cannot execute service %s with action %s",
                service_name,
                action_name,
            )
            return {}
        except FritzConnectionException:
            _LOGGER.exception(
                "Connection Error: Please check the device is properly configured"
                " for remote login"
            )
            return {}
        return result

    async def async_get_upnp_configuration(self) -> dict[str, Any]:
        """Call X_AVM-DE_UPnP service."""

        return await self._async_service_call("X_AVM-DE_UPnP", "1", "GetInfo")

    async def async_get_wan_link_properties(self) -> dict[str, Any]:
        """Call WANCommonInterfaceConfig service."""

        return await self._async_service_call(
            "WANCommonInterfaceConfig",
            "1",
            "GetCommonLinkProperties",
        )

    async def async_ipv6_active(self) -> bool:
        """Check ip an ipv6 is active on the WAn interface."""

        def wrap_external_ipv6() -> str:
            return str(self.fritz_status.external_ipv6)

        if not self.device_is_router:
            return False

        return bool(await self.hass.async_add_executor_job(wrap_external_ipv6))

    async def async_get_connection_info(self) -> ConnectionInfo:
        """Return ConnectionInfo data."""

        link_properties = await self.async_get_wan_link_properties()
        connection_info = ConnectionInfo(
            connection=link_properties.get("NewWANAccessType", "").lower(),
            mesh_role=self.mesh_role,
            wan_enabled=self.device_is_router,
            ipv6_active=await self.async_ipv6_active(),
        )
        _LOGGER.debug(
            "ConnectionInfo for FritzBox %s: %s",
            self.host,
            connection_info,
        )
        return connection_info

    async def async_get_num_port_mapping(self, con_type: str) -> dict[str, Any]:
        """Call GetPortMappingNumberOfEntries action."""

        return await self._async_service_call(
            con_type, "1", "GetPortMappingNumberOfEntries"
        )

    async def async_get_port_mapping(self, con_type: str, index: int) -> dict[str, Any]:
        """Call GetGenericPortMappingEntry action."""

        return await self._async_service_call(
            con_type, "1", "GetGenericPortMappingEntry", NewPortMappingIndex=index
        )

    async def async_get_wlan_configuration(self, index: int) -> dict[str, Any]:
        """Call WLANConfiguration service."""

        return await self._async_service_call(
            "WLANConfiguration", str(index), "GetInfo"
        )

    async def async_set_wlan_configuration(
        self, index: int, turn_on: bool
    ) -> dict[str, Any]:
        """Call SetEnable action from WLANConfiguration service."""

        return await self._async_service_call(
            "WLANConfiguration",
            str(index),
            "SetEnable",
            NewEnable="1" if turn_on else "0",
        )

    async def async_set_deflection_enable(
        self, index: int, turn_on: bool
    ) -> dict[str, Any]:
        """Call SetDeflectionEnable service."""

        return await self._async_service_call(
            "X_AVM-DE_OnTel",
            "1",
            "SetDeflectionEnable",
            NewDeflectionId=index,
            NewEnable="1" if turn_on else "0",
        )

    async def async_add_port_mapping(
        self, con_type: str, port_mapping: Any
    ) -> dict[str, Any]:
        """Call AddPortMapping service."""

        return await self._async_service_call(
            con_type,
            "1",
            "AddPortMapping",
            **port_mapping,
        )

    async def async_set_allow_wan_access(
        self, ip_address: str, turn_on: bool
    ) -> dict[str, Any]:
        """Call X_AVM-DE_HostFilter service."""

        return await self._async_service_call(
            "X_AVM-DE_HostFilter",
            "1",
            "DisallowWANAccessByIP",
            NewIPv4Address=ip_address,
            NewDisallow="0" if turn_on else "1",
        )

    async def async_wake_on_lan(self, mac_address: str) -> dict[str, Any]:
        """Call X_AVM-DE_WakeOnLANByMACAddress service."""

        return await self._async_service_call(
            "Hosts",
            "1",
            "X_AVM-DE_WakeOnLANByMACAddress",
            NewMACAddress=mac_address,
        )


@dataclass
class FritzData:
    """Storage class for platform global data."""

    tracked: dict = field(default_factory=dict)
    profile_switches: dict = field(default_factory=dict)
    wol_buttons: dict = field(default_factory=dict)


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
    init_state: bool


@dataclass
class ConnectionInfo:
    """Fritz sensor connection information class."""

    connection: str
    mesh_role: MeshRoles
    wan_enabled: bool
    ipv6_active: bool
