"""Switches for AVM Fritz!Box functions."""
from __future__ import annotations

from collections import OrderedDict
from functools import partial
import logging
from typing import Any

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzSecurityError,
    FritzServiceError,
)
import xmltodict

from homeassistant.components.network import async_get_source_ip
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .common import (
    FritzBoxBaseEntity,
    FritzBoxTools,
    FritzData,
    FritzDevice,
    FritzDeviceBase,
    SwitchInfo,
    device_filter_out_from_trackers,
)
from .const import (
    DATA_FRITZ,
    DOMAIN,
    SWITCH_TYPE_DEFLECTION,
    SWITCH_TYPE_PORTFORWARD,
    SWITCH_TYPE_WIFINETWORK,
)

_LOGGER = logging.getLogger(__name__)


async def async_service_call_action(
    fritzbox_tools: FritzBoxTools,
    service_name: str,
    service_suffix: str | None,
    action_name: str,
    **kwargs: Any,
) -> None | dict:
    """Return service details."""
    return await fritzbox_tools.hass.async_add_executor_job(
        partial(
            service_call_action,
            fritzbox_tools,
            service_name,
            service_suffix,
            action_name,
            **kwargs,
        )
    )


def service_call_action(
    fritzbox_tools: FritzBoxTools,
    service_name: str,
    service_suffix: str | None,
    action_name: str,
    **kwargs: Any,
) -> dict | None:
    """Return service details."""

    if f"{service_name}{service_suffix}" not in fritzbox_tools.connection.services:
        return None

    try:
        return fritzbox_tools.connection.call_action(  # type: ignore[no-any-return]
            f"{service_name}:{service_suffix}",
            action_name,
            **kwargs,
        )
    except FritzSecurityError:
        _LOGGER.error(
            "Authorization Error: Please check the provided credentials and verify that you can log into the web interface",
            exc_info=True,
        )
        return None
    except (FritzActionError, FritzActionFailedError, FritzServiceError):
        _LOGGER.error(
            "Service/Action Error: cannot execute service %s",
            service_name,
            exc_info=True,
        )
        return None
    except FritzConnectionException:
        _LOGGER.error(
            "Connection Error: Please check the device is properly configured for remote login",
            exc_info=True,
        )
        return None


def get_deflections(
    fritzbox_tools: FritzBoxTools, service_name: str
) -> list[OrderedDict[Any, Any]] | None:
    """Get deflection switch info."""

    deflection_list = service_call_action(
        fritzbox_tools,
        service_name,
        "1",
        "GetDeflections",
    )

    if not deflection_list:
        return []

    items = xmltodict.parse(deflection_list["NewDeflectionList"])["List"]["Item"]
    if not isinstance(items, list):
        return [items]
    return items


def deflection_entities_list(
    fritzbox_tools: FritzBoxTools, device_friendly_name: str
) -> list[FritzBoxDeflectionSwitch]:
    """Get list of deflection entities."""

    _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_DEFLECTION)

    service_name = "X_AVM-DE_OnTel"
    deflections_response = service_call_action(
        fritzbox_tools, service_name, "1", "GetNumberOfDeflections"
    )
    if not deflections_response:
        _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_DEFLECTION)
        return []

    _LOGGER.debug(
        "Specific %s response: GetNumberOfDeflections=%s",
        SWITCH_TYPE_DEFLECTION,
        deflections_response,
    )

    if deflections_response["NewNumberOfDeflections"] == 0:
        _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_DEFLECTION)
        return []

    deflection_list = get_deflections(fritzbox_tools, service_name)
    if deflection_list is None:
        return []

    return [
        FritzBoxDeflectionSwitch(
            fritzbox_tools, device_friendly_name, dict_of_deflection
        )
        for dict_of_deflection in deflection_list
    ]


def port_entities_list(
    fritzbox_tools: FritzBoxTools, device_friendly_name: str, local_ip: str
) -> list[FritzBoxPortSwitch]:
    """Get list of port forwarding entities."""

    _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_PORTFORWARD)
    entities_list: list[FritzBoxPortSwitch] = []
    service_name = "Layer3Forwarding"
    connection_type = service_call_action(
        fritzbox_tools, service_name, "1", "GetDefaultConnectionService"
    )
    if not connection_type:
        _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_PORTFORWARD)
        return []

    # Return NewDefaultConnectionService sample: "1.WANPPPConnection.1"
    con_type: str = connection_type["NewDefaultConnectionService"][2:][:-2]

    # Query port forwardings and setup a switch for each forward for the current device
    resp = service_call_action(
        fritzbox_tools, con_type, "1", "GetPortMappingNumberOfEntries"
    )
    if not resp:
        _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_DEFLECTION)
        return []

    port_forwards_count: int = resp["NewPortMappingNumberOfEntries"]

    _LOGGER.debug(
        "Specific %s response: GetPortMappingNumberOfEntries=%s",
        SWITCH_TYPE_PORTFORWARD,
        port_forwards_count,
    )

    _LOGGER.debug("IP source for %s is %s", fritzbox_tools.host, local_ip)

    for i in range(port_forwards_count):

        portmap = service_call_action(
            fritzbox_tools,
            con_type,
            "1",
            "GetGenericPortMappingEntry",
            NewPortMappingIndex=i,
        )

        if not portmap:
            _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_DEFLECTION)
            continue

        _LOGGER.debug(
            "Specific %s response: GetGenericPortMappingEntry=%s",
            SWITCH_TYPE_PORTFORWARD,
            portmap,
        )

        # We can only handle port forwards of the given device
        if portmap["NewInternalClient"] == local_ip:
            port_name = portmap["NewPortMappingDescription"]
            for entity in entities_list:
                if entity.port_mapping and (
                    port_name in entity.port_mapping["NewPortMappingDescription"]
                ):
                    port_name = f"{port_name} {portmap['NewExternalPort']}"
            entities_list.append(
                FritzBoxPortSwitch(
                    fritzbox_tools,
                    device_friendly_name,
                    portmap,
                    port_name,
                    i,
                    con_type,
                )
            )

    return entities_list


def wifi_entities_list(
    fritzbox_tools: FritzBoxTools, device_friendly_name: str
) -> list[FritzBoxWifiSwitch]:
    """Get list of wifi entities."""
    _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_WIFINETWORK)
    std_table = {"ax": "Wifi6", "ac": "5Ghz", "n": "2.4Ghz"}
    networks: dict = {}
    for i in range(4):
        if not ("WLANConfiguration" + str(i)) in fritzbox_tools.connection.services:
            continue

        network_info = service_call_action(
            fritzbox_tools, "WLANConfiguration", str(i), "GetInfo"
        )
        if network_info:
            ssid = network_info["NewSSID"]
            _LOGGER.debug("SSID from device: <%s>", ssid)
            if (
                slugify(
                    ssid,
                )
                in [slugify(v) for v in networks.values()]
            ):
                _LOGGER.debug("SSID duplicated, adding suffix")
                networks[i] = f'{ssid} {std_table[network_info["NewStandard"]]}'
            else:
                networks[i] = ssid
            _LOGGER.debug("SSID normalized: <%s>", networks[i])

    return [
        FritzBoxWifiSwitch(fritzbox_tools, device_friendly_name, net, network_name)
        for net, network_name in networks.items()
    ]


def profile_entities_list(
    router: FritzBoxTools,
    data_fritz: FritzData,
) -> list[FritzBoxProfileSwitch]:
    """Add new tracker entities from the router."""

    new_profiles: list[FritzBoxProfileSwitch] = []

    if "X_AVM-DE_HostFilter1" not in router.connection.services:
        return new_profiles

    if router.unique_id not in data_fritz.profile_switches:
        data_fritz.profile_switches[router.unique_id] = set()

    for mac, device in router.devices.items():
        if device_filter_out_from_trackers(
            mac, device, data_fritz.profile_switches.values()
        ):
            continue

        new_profiles.append(FritzBoxProfileSwitch(router, device))
        data_fritz.profile_switches[router.unique_id].add(mac)

    return new_profiles


def all_entities_list(
    fritzbox_tools: FritzBoxTools,
    device_friendly_name: str,
    data_fritz: FritzData,
    local_ip: str,
) -> list[Entity]:
    """Get a list of all entities."""
    return [
        *deflection_entities_list(fritzbox_tools, device_friendly_name),
        *port_entities_list(fritzbox_tools, device_friendly_name, local_ip),
        *wifi_entities_list(fritzbox_tools, device_friendly_name),
        *profile_entities_list(fritzbox_tools, data_fritz),
    ]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up switches")
    fritzbox_tools: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]
    data_fritz: FritzData = hass.data[DATA_FRITZ]

    _LOGGER.debug("Fritzbox services: %s", fritzbox_tools.connection.services)

    local_ip = await async_get_source_ip(
        fritzbox_tools.hass, target_ip=fritzbox_tools.host
    )

    entities_list = await hass.async_add_executor_job(
        all_entities_list,
        fritzbox_tools,
        entry.title,
        data_fritz,
        local_ip,
    )

    async_add_entities(entities_list)

    @callback
    def update_router() -> None:
        """Update the values of the router."""
        async_add_entities(profile_entities_list(fritzbox_tools, data_fritz))

    entry.async_on_unload(
        async_dispatcher_connect(hass, fritzbox_tools.signal_device_new, update_router)
    )


class FritzBoxBaseSwitch(FritzBoxBaseEntity):
    """Fritz switch base class."""

    def __init__(
        self,
        fritzbox_tools: FritzBoxTools,
        device_friendly_name: str,
        switch_info: SwitchInfo,
    ) -> None:
        """Init Fritzbox port switch."""
        super().__init__(fritzbox_tools, device_friendly_name)

        self._description = switch_info["description"]
        self._friendly_name = switch_info["friendly_name"]
        self._icon = switch_info["icon"]
        self._type = switch_info["type"]
        self._update = switch_info["callback_update"]
        self._switch = switch_info["callback_switch"]

        self._name = f"{self._friendly_name} {self._description}"
        self._unique_id = (
            f"{self._fritzbox_tools.unique_id}-{slugify(self._description)}"
        )

        self._attributes: dict[str, str] = {}
        self._is_available = True

        self._attr_is_on = False

    @property
    def name(self) -> str:
        """Return name."""
        return self._name

    @property
    def icon(self) -> str:
        """Return name."""
        return self._icon

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._is_available

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return device attributes."""
        return self._attributes

    async def async_update(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating '%s' (%s) switch state", self.name, self._type)
        await self._update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self._async_handle_turn_on_off(turn_on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self._async_handle_turn_on_off(turn_on=False)

    async def _async_handle_turn_on_off(self, turn_on: bool) -> None:
        """Handle switch state change request."""
        await self._switch(turn_on)
        self._attr_is_on = turn_on


class FritzBoxPortSwitch(FritzBoxBaseSwitch, SwitchEntity):
    """Defines a FRITZ!Box Tools PortForward switch."""

    def __init__(
        self,
        fritzbox_tools: FritzBoxTools,
        device_friendly_name: str,
        port_mapping: dict[str, Any] | None,
        port_name: str,
        idx: int,
        connection_type: str,
    ) -> None:
        """Init Fritzbox port switch."""
        self._fritzbox_tools = fritzbox_tools

        self._attributes = {}
        self.connection_type = connection_type
        self.port_mapping = port_mapping  # dict in the format as it comes from fritzconnection. eg: {'NewRemoteHost': '0.0.0.0', 'NewExternalPort': 22, 'NewProtocol': 'TCP', 'NewInternalPort': 22, 'NewInternalClient': '192.168.178.31', 'NewEnabled': True, 'NewPortMappingDescription': 'Beast SSH ', 'NewLeaseDuration': 0}
        self._idx = idx  # needed for update routine

        if port_mapping is None:
            return

        switch_info = SwitchInfo(
            description=f"Port forward {port_name}",
            friendly_name=device_friendly_name,
            icon="mdi:check-network",
            type=SWITCH_TYPE_PORTFORWARD,
            callback_update=self._async_fetch_update,
            callback_switch=self._async_handle_port_switch_on_off,
        )
        super().__init__(fritzbox_tools, device_friendly_name, switch_info)

    async def _async_fetch_update(self) -> None:
        """Fetch updates."""

        self.port_mapping = await async_service_call_action(
            self._fritzbox_tools,
            self.connection_type,
            "1",
            "GetGenericPortMappingEntry",
            NewPortMappingIndex=self._idx,
        )
        _LOGGER.debug(
            "Specific %s response: %s", SWITCH_TYPE_PORTFORWARD, self.port_mapping
        )
        if self.port_mapping is None:
            self._is_available = False
            return

        self._attr_is_on = self.port_mapping["NewEnabled"] is True
        self._is_available = True

        attributes_dict = {
            "NewInternalClient": "internal_ip",
            "NewInternalPort": "internal_port",
            "NewExternalPort": "external_port",
            "NewProtocol": "protocol",
            "NewPortMappingDescription": "description",
        }

        for key, attr in attributes_dict.items():
            self._attributes[attr] = self.port_mapping[key]

    async def _async_handle_port_switch_on_off(self, turn_on: bool) -> bool:

        if self.port_mapping is None:
            return False

        self.port_mapping["NewEnabled"] = "1" if turn_on else "0"

        resp = await async_service_call_action(
            self._fritzbox_tools,
            self.connection_type,
            "1",
            "AddPortMapping",
            **self.port_mapping,
        )

        return bool(resp is not None)


class FritzBoxDeflectionSwitch(FritzBoxBaseSwitch, SwitchEntity):
    """Defines a FRITZ!Box Tools PortForward switch."""

    def __init__(
        self,
        fritzbox_tools: FritzBoxTools,
        device_friendly_name: str,
        dict_of_deflection: Any,
    ) -> None:
        """Init Fritxbox Deflection class."""
        self._fritzbox_tools: FritzBoxTools = fritzbox_tools

        self.dict_of_deflection = dict_of_deflection
        self._attributes = {}
        self.id = int(self.dict_of_deflection["DeflectionId"])

        switch_info = SwitchInfo(
            description=f"Call deflection {self.id}",
            friendly_name=device_friendly_name,
            icon="mdi:phone-forward",
            type=SWITCH_TYPE_DEFLECTION,
            callback_update=self._async_fetch_update,
            callback_switch=self._async_switch_on_off_executor,
        )
        super().__init__(self._fritzbox_tools, device_friendly_name, switch_info)

    async def _async_fetch_update(self) -> None:
        """Fetch updates."""

        resp = await async_service_call_action(
            self._fritzbox_tools, "X_AVM-DE_OnTel", "1", "GetDeflections"
        )
        if not resp:
            self._is_available = False
            return

        self.dict_of_deflection = xmltodict.parse(resp["NewDeflectionList"])["List"][
            "Item"
        ]
        if isinstance(self.dict_of_deflection, list):
            self.dict_of_deflection = self.dict_of_deflection[self.id]

        _LOGGER.debug(
            "Specific %s response: NewDeflectionList=%s",
            SWITCH_TYPE_DEFLECTION,
            self.dict_of_deflection,
        )

        self._attr_is_on = self.dict_of_deflection["Enable"] == "1"
        self._is_available = True

        self._attributes["type"] = self.dict_of_deflection["Type"]
        self._attributes["number"] = self.dict_of_deflection["Number"]
        self._attributes["deflection_to_number"] = self.dict_of_deflection[
            "DeflectionToNumber"
        ]
        # Return mode sample: "eImmediately"
        self._attributes["mode"] = self.dict_of_deflection["Mode"][1:]
        self._attributes["outgoing"] = self.dict_of_deflection["Outgoing"]
        self._attributes["phonebook_id"] = self.dict_of_deflection["PhonebookID"]

    async def _async_switch_on_off_executor(self, turn_on: bool) -> None:
        """Handle deflection switch."""
        await async_service_call_action(
            self._fritzbox_tools,
            "X_AVM-DE_OnTel",
            "1",
            "SetDeflectionEnable",
            NewDeflectionId=self.id,
            NewEnable="1" if turn_on else "0",
        )


class FritzBoxProfileSwitch(FritzDeviceBase, SwitchEntity):
    """Defines a FRITZ!Box Tools DeviceProfile switch."""

    _attr_icon = "mdi:router-wireless-settings"

    def __init__(self, fritzbox_tools: FritzBoxTools, device: FritzDevice) -> None:
        """Init Fritz profile."""
        super().__init__(fritzbox_tools, device)
        self._attr_is_on: bool = False
        self._name = f"{device.hostname} Internet Access"
        self._attr_unique_id = f"{self._mac}_internet_access"

    async def async_process_update(self) -> None:
        """Update device."""
        if not self._mac or not self.ip_address:
            return

        wan_disable_info = await async_service_call_action(
            self._router,
            "X_AVM-DE_HostFilter",
            "1",
            "GetWANAccessByIP",
            NewIPv4Address=self.ip_address,
        )

        if wan_disable_info is None:
            return

        self._attr_is_on = not wan_disable_info["NewDisallow"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self._async_handle_turn_on_off(turn_on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self._async_handle_turn_on_off(turn_on=False)

    async def _async_handle_turn_on_off(self, turn_on: bool) -> bool:
        """Handle switch state change request."""
        await self._async_switch_on_off(turn_on)
        self._attr_is_on = turn_on
        self.async_write_ha_state()
        return True

    async def _async_switch_on_off(self, turn_on: bool) -> None:
        """Handle parental control switch."""
        await async_service_call_action(
            self._router,
            "X_AVM-DE_HostFilter",
            "1",
            "DisallowWANAccessByIP",
            NewIPv4Address=self.ip_address,
            NewDisallow="0" if turn_on else "1",
        )


class FritzBoxWifiSwitch(FritzBoxBaseSwitch, SwitchEntity):
    """Defines a FRITZ!Box Tools Wifi switch."""

    def __init__(
        self,
        fritzbox_tools: FritzBoxTools,
        device_friendly_name: str,
        network_num: int,
        network_name: str,
    ) -> None:
        """Init Fritz Wifi switch."""
        self._fritzbox_tools = fritzbox_tools

        self._attributes = {}
        self._network_num = network_num

        switch_info = SwitchInfo(
            description=f"Wi-Fi {network_name}",
            friendly_name=device_friendly_name,
            icon="mdi:wifi",
            type=SWITCH_TYPE_WIFINETWORK,
            callback_update=self._async_fetch_update,
            callback_switch=self._async_switch_on_off_executor,
        )
        super().__init__(self._fritzbox_tools, device_friendly_name, switch_info)

    async def _async_fetch_update(self) -> None:
        """Fetch updates."""

        wifi_info = await async_service_call_action(
            self._fritzbox_tools,
            "WLANConfiguration",
            str(self._network_num),
            "GetInfo",
        )
        _LOGGER.debug(
            "Specific %s response: GetInfo=%s", SWITCH_TYPE_WIFINETWORK, wifi_info
        )

        if wifi_info is None:
            self._is_available = False
            return

        self._attr_is_on = wifi_info["NewEnable"] is True
        self._is_available = True

        std = wifi_info["NewStandard"]
        self._attributes["standard"] = std if std else None
        self._attributes["bssid"] = wifi_info["NewBSSID"]
        self._attributes["mac_address_control"] = wifi_info[
            "NewMACAddressControlEnabled"
        ]

    async def _async_switch_on_off_executor(self, turn_on: bool) -> None:
        """Handle wifi switch."""
        await async_service_call_action(
            self._fritzbox_tools,
            "WLANConfiguration",
            str(self._network_num),
            "SetEnable",
            NewEnable="1" if turn_on else "0",
        )
