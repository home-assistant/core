"""Switches for AVM Fritz!Box functions."""
from __future__ import annotations

import logging
from typing import Any

import xmltodict

from homeassistant.components.network import async_get_source_ip
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .common import (
    AvmWrapper,
    FritzBoxBaseEntity,
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
    SWITCH_TYPE_PROFILE,
    SWITCH_TYPE_WIFINETWORK,
    WIFI_STANDARD,
    MeshRoles,
)

_LOGGER = logging.getLogger(__name__)


async def _async_deflection_entities_list(
    avm_wrapper: AvmWrapper, device_friendly_name: str
) -> list[FritzBoxDeflectionSwitch]:
    """Get list of deflection entities."""

    _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_DEFLECTION)

    deflections_response = await avm_wrapper.async_get_ontel_num_deflections()
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

    if not (deflection_list := await avm_wrapper.async_get_ontel_deflections()):
        return []

    items = xmltodict.parse(deflection_list["NewDeflectionList"])["List"]["Item"]
    if not isinstance(items, list):
        items = [items]

    return [
        FritzBoxDeflectionSwitch(avm_wrapper, device_friendly_name, dict_of_deflection)
        for dict_of_deflection in items
    ]


async def _async_port_entities_list(
    avm_wrapper: AvmWrapper, device_friendly_name: str, local_ip: str
) -> list[FritzBoxPortSwitch]:
    """Get list of port forwarding entities."""

    _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_PORTFORWARD)
    entities_list: list[FritzBoxPortSwitch] = []
    if not avm_wrapper.device_conn_type:
        _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_PORTFORWARD)
        return []

    # Query port forwardings and setup a switch for each forward for the current device
    resp = await avm_wrapper.async_get_num_port_mapping(avm_wrapper.device_conn_type)
    if not resp:
        _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_DEFLECTION)
        return []

    port_forwards_count: int = resp["NewPortMappingNumberOfEntries"]

    _LOGGER.debug(
        "Specific %s response: GetPortMappingNumberOfEntries=%s",
        SWITCH_TYPE_PORTFORWARD,
        port_forwards_count,
    )

    _LOGGER.debug("IP source for %s is %s", avm_wrapper.host, local_ip)

    for i in range(port_forwards_count):
        portmap = await avm_wrapper.async_get_port_mapping(
            avm_wrapper.device_conn_type, i
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
                    avm_wrapper,
                    device_friendly_name,
                    portmap,
                    port_name,
                    i,
                    avm_wrapper.device_conn_type,
                )
            )

    return entities_list


async def _async_wifi_entities_list(
    avm_wrapper: AvmWrapper, device_friendly_name: str
) -> list[FritzBoxWifiSwitch]:
    """Get list of wifi entities."""
    _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_WIFINETWORK)

    #
    # https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf
    #
    wifi_count = len(
        [
            s
            for s in avm_wrapper.connection.services
            if s.startswith("WLANConfiguration")
        ]
    )
    _LOGGER.debug("WiFi networks count: %s", wifi_count)
    networks: dict = {}
    for i in range(1, wifi_count + 1):
        network_info = await avm_wrapper.async_get_wlan_configuration(i)
        # Devices with 4 WLAN services, use the 2nd for internal communications
        if not (wifi_count == 4 and i == 2):
            networks[i] = {
                "ssid": network_info["NewSSID"],
                "bssid": network_info["NewBSSID"],
                "standard": network_info["NewStandard"],
                "enabled": network_info["NewEnable"],
                "status": network_info["NewStatus"],
            }
    for i, network in networks.copy().items():
        networks[i]["switch_name"] = network["ssid"]
        if (
            len(
                [
                    j
                    for j, n in networks.items()
                    if slugify(n["ssid"]) == slugify(network["ssid"])
                ]
            )
            > 1
        ):
            networks[i]["switch_name"] += f" ({WIFI_STANDARD[i]})"

    _LOGGER.debug("WiFi networks list: %s", networks)
    return [
        FritzBoxWifiSwitch(
            avm_wrapper, device_friendly_name, index, data["switch_name"]
        )
        for index, data in networks.items()
    ]


async def _async_profile_entities_list(
    avm_wrapper: AvmWrapper,
    data_fritz: FritzData,
) -> list[FritzBoxProfileSwitch]:
    """Add new tracker entities from the AVM device."""
    _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_PROFILE)

    new_profiles: list[FritzBoxProfileSwitch] = []

    if "X_AVM-DE_HostFilter1" not in avm_wrapper.connection.services:
        return new_profiles

    if avm_wrapper.unique_id not in data_fritz.profile_switches:
        data_fritz.profile_switches[avm_wrapper.unique_id] = set()

    for mac, device in avm_wrapper.devices.items():
        if device_filter_out_from_trackers(
            mac, device, data_fritz.profile_switches.values()
        ):
            _LOGGER.debug(
                "Skipping profile switch creation for device %s", device.hostname
            )
            continue

        new_profiles.append(FritzBoxProfileSwitch(avm_wrapper, device))
        data_fritz.profile_switches[avm_wrapper.unique_id].add(mac)

    _LOGGER.debug("Creating %s profile switches", len(new_profiles))
    return new_profiles


async def async_all_entities_list(
    avm_wrapper: AvmWrapper,
    device_friendly_name: str,
    data_fritz: FritzData,
    local_ip: str,
) -> list[Entity]:
    """Get a list of all entities."""

    if avm_wrapper.mesh_role == MeshRoles.SLAVE:
        return []

    return [
        *await _async_deflection_entities_list(avm_wrapper, device_friendly_name),
        *await _async_port_entities_list(avm_wrapper, device_friendly_name, local_ip),
        *await _async_wifi_entities_list(avm_wrapper, device_friendly_name),
        *await _async_profile_entities_list(avm_wrapper, data_fritz),
    ]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up switches")
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]
    data_fritz: FritzData = hass.data[DATA_FRITZ]

    _LOGGER.debug("Fritzbox services: %s", avm_wrapper.connection.services)

    local_ip = await async_get_source_ip(avm_wrapper.hass, target_ip=avm_wrapper.host)

    entities_list = await async_all_entities_list(
        avm_wrapper,
        entry.title,
        data_fritz,
        local_ip,
    )

    async_add_entities(entities_list)

    @callback
    async def async_update_avm_device() -> None:
        """Update the values of the AVM device."""
        async_add_entities(await _async_profile_entities_list(avm_wrapper, data_fritz))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, avm_wrapper.signal_device_new, async_update_avm_device
        )
    )


class FritzBoxBaseSwitch(FritzBoxBaseEntity):
    """Fritz switch base class."""

    _attr_is_on: bool | None = False

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        switch_info: SwitchInfo,
    ) -> None:
        """Init Fritzbox port switch."""
        super().__init__(avm_wrapper, device_friendly_name)

        self._description = switch_info["description"]
        self._friendly_name = switch_info["friendly_name"]
        self._icon = switch_info["icon"]
        self._type = switch_info["type"]
        self._update = switch_info["callback_update"]
        self._switch = switch_info["callback_switch"]

        self._name = f"{self._friendly_name} {self._description}"
        self._unique_id = f"{self._avm_wrapper.unique_id}-{slugify(self._description)}"

        self._attributes: dict[str, str] = {}
        self._is_available = True

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
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        port_mapping: dict[str, Any] | None,
        port_name: str,
        idx: int,
        connection_type: str,
    ) -> None:
        """Init Fritzbox port switch."""
        self._avm_wrapper = avm_wrapper

        self._attributes = {}
        self.connection_type = connection_type
        self.port_mapping = port_mapping  # dict in the format as it comes from fritzconnection. eg: {'NewRemoteHost': '0.0.0.0', 'NewExternalPort': 22, 'NewProtocol': 'TCP', 'NewInternalPort': 22, 'NewInternalClient': '192.168.178.31', 'NewEnabled': True, 'NewPortMappingDescription': 'Beast SSH ', 'NewLeaseDuration': 0}
        self._idx = idx  # needed for update routine
        self._attr_entity_category = EntityCategory.CONFIG

        if port_mapping is None:
            return

        switch_info = SwitchInfo(
            description=f"Port forward {port_name}",
            friendly_name=device_friendly_name,
            icon="mdi:check-network",
            type=SWITCH_TYPE_PORTFORWARD,
            callback_update=self._async_fetch_update,
            callback_switch=self._async_switch_on_off_executor,
        )
        super().__init__(avm_wrapper, device_friendly_name, switch_info)

    async def _async_fetch_update(self) -> None:
        """Fetch updates."""

        self.port_mapping = await self._avm_wrapper.async_get_port_mapping(
            self.connection_type, self._idx
        )
        _LOGGER.debug(
            "Specific %s response: %s", SWITCH_TYPE_PORTFORWARD, self.port_mapping
        )
        if not self.port_mapping:
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

    async def _async_switch_on_off_executor(self, turn_on: bool) -> bool:
        if self.port_mapping is None:
            return False

        self.port_mapping["NewEnabled"] = "1" if turn_on else "0"

        resp = await self._avm_wrapper.async_add_port_mapping(
            self.connection_type, self.port_mapping
        )
        return bool(resp is not None)


class FritzBoxDeflectionSwitch(FritzBoxBaseSwitch, SwitchEntity):
    """Defines a FRITZ!Box Tools PortForward switch."""

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        dict_of_deflection: Any,
    ) -> None:
        """Init Fritxbox Deflection class."""
        self._avm_wrapper = avm_wrapper

        self.dict_of_deflection = dict_of_deflection
        self._attributes = {}
        self.id = int(self.dict_of_deflection["DeflectionId"])
        self._attr_entity_category = EntityCategory.CONFIG

        switch_info = SwitchInfo(
            description=f"Call deflection {self.id}",
            friendly_name=device_friendly_name,
            icon="mdi:phone-forward",
            type=SWITCH_TYPE_DEFLECTION,
            callback_update=self._async_fetch_update,
            callback_switch=self._async_switch_on_off_executor,
        )
        super().__init__(self._avm_wrapper, device_friendly_name, switch_info)

    async def _async_fetch_update(self) -> None:
        """Fetch updates."""

        resp = await self._avm_wrapper.async_get_ontel_deflections()
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
        await self._avm_wrapper.async_set_deflection_enable(self.id, turn_on)


class FritzBoxProfileSwitch(FritzDeviceBase, SwitchEntity):
    """Defines a FRITZ!Box Tools DeviceProfile switch."""

    _attr_icon = "mdi:router-wireless-settings"

    def __init__(self, avm_wrapper: AvmWrapper, device: FritzDevice) -> None:
        """Init Fritz profile."""
        super().__init__(avm_wrapper, device)
        self._attr_is_on: bool = False
        self._name = f"{device.hostname} Internet Access"
        self._attr_unique_id = f"{self._mac}_internet_access"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
            default_manufacturer="AVM",
            default_model="FRITZ!Box Tracked device",
            default_name=device.hostname,
            identifiers={(DOMAIN, self._mac)},
            via_device=(
                DOMAIN,
                avm_wrapper.unique_id,
            ),
        )

    @property
    def is_on(self) -> bool | None:
        """Switch status."""
        return self._avm_wrapper.devices[self._mac].wan_access

    @property
    def available(self) -> bool:
        """Return availability of the switch."""
        if self._avm_wrapper.devices[self._mac].wan_access is None:
            return False
        return super().available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self._async_handle_turn_on_off(turn_on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self._async_handle_turn_on_off(turn_on=False)

    async def _async_handle_turn_on_off(self, turn_on: bool) -> bool:
        """Handle switch state change request."""
        if not self.ip_address:
            return False
        await self._avm_wrapper.async_set_allow_wan_access(self.ip_address, turn_on)
        self.async_write_ha_state()
        return True


class FritzBoxWifiSwitch(FritzBoxBaseSwitch, SwitchEntity):
    """Defines a FRITZ!Box Tools Wifi switch."""

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        network_num: int,
        network_name: str,
    ) -> None:
        """Init Fritz Wifi switch."""
        self._avm_wrapper = avm_wrapper

        self._attributes = {}
        self._attr_entity_category = EntityCategory.CONFIG
        self._network_num = network_num

        switch_info = SwitchInfo(
            description=f"Wi-Fi {network_name}",
            friendly_name=device_friendly_name,
            icon="mdi:wifi",
            type=SWITCH_TYPE_WIFINETWORK,
            callback_update=self._async_fetch_update,
            callback_switch=self._async_switch_on_off_executor,
        )
        super().__init__(self._avm_wrapper, device_friendly_name, switch_info)

    async def _async_fetch_update(self) -> None:
        """Fetch updates."""

        wifi_info = await self._avm_wrapper.async_get_wlan_configuration(
            self._network_num
        )
        _LOGGER.debug(
            "Specific %s response: GetInfo=%s", SWITCH_TYPE_WIFINETWORK, wifi_info
        )

        if not wifi_info:
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
        await self._avm_wrapper.async_set_wlan_configuration(self._network_num, turn_on)
