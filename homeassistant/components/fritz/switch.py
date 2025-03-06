"""Switches for AVM Fritz!Box functions."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.network import async_get_source_ip
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    SWITCH_TYPE_DEFLECTION,
    SWITCH_TYPE_PORTFORWARD,
    SWITCH_TYPE_PROFILE,
    SWITCH_TYPE_WIFINETWORK,
    WIFI_STANDARD,
    MeshRoles,
)
from .coordinator import (
    FRITZ_DATA_KEY,
    AvmWrapper,
    FritzConfigEntry,
    FritzData,
    FritzDevice,
    SwitchInfo,
    device_filter_out_from_trackers,
)
from .entity import FritzBoxBaseEntity, FritzDeviceBase

_LOGGER = logging.getLogger(__name__)


async def _async_deflection_entities_list(
    avm_wrapper: AvmWrapper, device_friendly_name: str
) -> list[FritzBoxDeflectionSwitch]:
    """Get list of deflection entities."""

    _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_DEFLECTION)

    if not (call_deflections := avm_wrapper.data["call_deflections"]):
        _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_DEFLECTION)
        return []

    return [
        FritzBoxDeflectionSwitch(avm_wrapper, device_friendly_name, cd_id)
        for cd_id in call_deflections
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
        _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_PORTFORWARD)
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
        FritzBoxWifiSwitch(avm_wrapper, device_friendly_name, index, data)
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
        if not avm_wrapper.mesh_wifi_uplink:
            return [*await _async_wifi_entities_list(avm_wrapper, device_friendly_name)]
        return []

    return [
        *await _async_deflection_entities_list(avm_wrapper, device_friendly_name),
        *await _async_port_entities_list(avm_wrapper, device_friendly_name, local_ip),
        *await _async_wifi_entities_list(avm_wrapper, device_friendly_name),
        *await _async_profile_entities_list(avm_wrapper, data_fritz),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up switches")
    avm_wrapper = entry.runtime_data
    data_fritz = hass.data[FRITZ_DATA_KEY]

    _LOGGER.debug("Fritzbox services: %s", avm_wrapper.connection.services)

    local_ip = await async_get_source_ip(avm_wrapper.hass, target_ip=avm_wrapper.host)

    entities_list = await async_all_entities_list(
        avm_wrapper,
        entry.title,
        data_fritz,
        local_ip,
    )

    async_add_entities(entities_list)

    async def async_update_avm_device() -> None:
        """Update the values of the AVM device."""
        async_add_entities(await _async_profile_entities_list(avm_wrapper, data_fritz))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, avm_wrapper.signal_device_new, async_update_avm_device
        )
    )


class FritzBoxBaseCoordinatorSwitch(CoordinatorEntity[AvmWrapper], SwitchEntity):
    """Fritz switch coordinator base class."""

    entity_description: SwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_name: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Init device info class."""
        super().__init__(avm_wrapper)
        self.entity_description = description
        self._device_name = device_name
        self._attr_unique_id = f"{avm_wrapper.unique_id}-{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            configuration_url=f"http://{self.coordinator.host}",
            connections={(CONNECTION_NETWORK_MAC, self.coordinator.mac)},
            identifiers={(DOMAIN, self.coordinator.unique_id)},
            manufacturer="AVM",
            model=self.coordinator.model,
            name=self._device_name,
            sw_version=self.coordinator.current_firmware,
        )

    @property
    def data(self) -> dict[str, Any]:
        """Return entity data from coordinator data."""
        raise NotImplementedError

    @property
    def available(self) -> bool:
        """Return availability based on data availability."""
        return super().available and bool(self.data)

    async def _async_handle_turn_on_off(self, turn_on: bool) -> None:
        """Handle switch state change request."""
        raise NotImplementedError

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self._async_handle_turn_on_off(turn_on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self._async_handle_turn_on_off(turn_on=False)


class FritzBoxBaseSwitch(FritzBoxBaseEntity, SwitchEntity):
    """Fritz switch base class."""

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        switch_info: SwitchInfo,
    ) -> None:
        """Init Fritzbox base switch."""
        super().__init__(avm_wrapper, device_friendly_name)

        self._description = switch_info["description"]
        self._friendly_name = switch_info["friendly_name"]
        self._icon = switch_info["icon"]
        self._type = switch_info["type"]
        self._update = switch_info["callback_update"]
        self._switch = switch_info["callback_switch"]
        self._attr_is_on = switch_info["init_state"]

        self._name = f"{self._friendly_name} {self._description}"
        self._unique_id = f"{self._avm_wrapper.unique_id}-{slugify(self._description)}"

        self._attributes: dict[str, str | None] = {}
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
    def extra_state_attributes(self) -> dict[str, str | None]:
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


class FritzBoxPortSwitch(FritzBoxBaseSwitch):
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
            init_state=port_mapping["NewEnabled"],
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


class FritzBoxDeflectionSwitch(FritzBoxBaseCoordinatorSwitch):
    """Defines a FRITZ!Box Tools PortForward switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        deflection_id: int,
    ) -> None:
        """Init Fritxbox Deflection class."""
        self.deflection_id = deflection_id
        description = SwitchEntityDescription(
            key=f"call_deflection_{self.deflection_id}",
            name=f"Call deflection {self.deflection_id}",
            icon="mdi:phone-forward",
        )
        super().__init__(avm_wrapper, device_friendly_name, description)

    @property
    def data(self) -> dict[str, Any]:
        """Return call deflection data."""
        return self.coordinator.data["call_deflections"].get(self.deflection_id, {})

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return device attributes."""
        return {
            "type": self.data["Type"],
            "number": self.data["Number"],
            "deflection_to_number": self.data["DeflectionToNumber"],
            "mode": self.data["Mode"][1:],
            "outgoing": self.data["Outgoing"],
            "phonebook_id": self.data["PhonebookID"],
        }

    @property
    def is_on(self) -> bool | None:
        """Switch status."""
        return self.data.get("Enable") == "1"

    async def _async_handle_turn_on_off(self, turn_on: bool) -> None:
        """Handle deflection switch."""
        await self.coordinator.async_set_deflection_enable(self.deflection_id, turn_on)


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


class FritzBoxWifiSwitch(FritzBoxBaseSwitch):
    """Defines a FRITZ!Box Tools Wifi switch."""

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        network_num: int,
        network_data: dict,
    ) -> None:
        """Init Fritz Wifi switch."""
        self._avm_wrapper = avm_wrapper

        self._attributes = {}
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = (
            avm_wrapper.mesh_role is not MeshRoles.SLAVE
        )
        self._network_num = network_num

        switch_info = SwitchInfo(
            description=f"Wi-Fi {network_data['switch_name']}",
            friendly_name=device_friendly_name,
            icon="mdi:wifi",
            type=SWITCH_TYPE_WIFINETWORK,
            callback_update=self._async_fetch_update,
            callback_switch=self._async_switch_on_off_executor,
            init_state=network_data["enabled"],
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
