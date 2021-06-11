"""Switches for AVM Fritz!Box functions."""
from __future__ import annotations

import logging

from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError
import xmltodict

from homeassistant.components.network.util import async_get_source_ip
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import FritzBoxBaseSwitch, FritzBoxTools, SwitchInfo
from .const import (
    DOMAIN,
    SWITCH_TYPE_DEFLECTION,
    SWITCH_TYPE_DEVICEPROFILE,
    SWITCH_TYPE_PORTFORWARD,
    SWITCH_TYPE_WIFINETWORK,
)

_LOGGER = logging.getLogger(__name__)


def service_call_action(
    fritzbox_tools: FritzBoxTools,
    service_name: str,
    service_suffix: bool,
    action_name: str,
    **kwargs,
) -> None | dict:
    """Return service details."""

    service_append = "1" if service_suffix else ""
    if (service_name + service_append) not in fritzbox_tools.connection.services:
        return None

    try:
        service_append = ":1" if service_suffix else ""
        return fritzbox_tools.connection.call_action(
            (service_name + service_append), action_name, **kwargs
        )
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error(
            "Call action cannot execute service %s",
            service_name,
            exc_info=True,
        )
        return None


def get_deflections(fritzbox_tools: FritzBoxTools, service_name: str) -> None | list:
    """Get deflection switch info."""

    deflection_list = service_call_action(
        fritzbox_tools,
        service_name,
        True,
        "GetDeflections",
    )

    if not deflection_list:
        return None

    deflections = xmltodict.parse(deflection_list["NewDeflectionList"])["List"]["Item"]

    if not isinstance(deflections, list):
        deflections = [deflections]

    return deflections


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up switches")
    fritzbox_tools: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug("Fritzbox services: %s", fritzbox_tools.connection.services)

    def _create_deflection_switches():

        _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_DEFLECTION)

        service_name = "X_AVM-DE_OnTel"
        deflections_response = service_call_action(
            fritzbox_tools, service_name, True, "GetNumberOfDeflections"
        )
        if not deflections_response:
            _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_DEFLECTION)
            return

        _LOGGER.debug(
            "Specific %s response: GetNumberOfDeflections=%s",
            SWITCH_TYPE_DEFLECTION,
            deflections_response,
        )

        if deflections_response["NewNumberOfDeflections"] != 0:
            for dict_of_deflection in get_deflections(fritzbox_tools, service_name):
                hass.add_job(
                    async_add_entities,
                    [
                        FritzBoxDeflectionSwitch(
                            fritzbox_tools, entry.title, dict_of_deflection
                        )
                    ],
                )

    def _create_port_switches():

        _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_PORTFORWARD)

        service_name = "Layer3Forwarding"
        connection_type = service_call_action(
            fritzbox_tools, service_name, True, "GetDefaultConnectionService"
        )
        if not connection_type:
            _LOGGER.debug("The FRITZ!Box has no %s options", SWITCH_TYPE_PORTFORWARD)
            return

        # Return NewDefaultConnectionService sample: "1.WANPPPConnection.1"
        connection_type = connection_type["NewDefaultConnectionService"][2:][:-2]

        # Query port forwardings and setup a switch for each forward for the current device
        port_forwards_count: int = service_call_action(
            fritzbox_tools, connection_type, True, "GetPortMappingNumberOfEntries"
        )["NewPortMappingNumberOfEntries"]

        _LOGGER.debug(
            "Specific %s response: GetPortMappingNumberOfEntries=%s",
            SWITCH_TYPE_PORTFORWARD,
            port_forwards_count,
        )

        for i in range(port_forwards_count):

            portmap = service_call_action(
                fritzbox_tools,
                connection_type,
                True,
                "GetGenericPortMappingEntry",
                NewPortMappingIndex=i,
            )

            if not portmap:
                return None

            _LOGGER.debug(
                "Specific %s response: GetGenericPortMappingEntry=%s",
                SWITCH_TYPE_PORTFORWARD,
                portmap,
            )

            # We can only handle port forwards of the given device
            local_ip = async_get_source_ip(fritzbox_tools.host)
            _LOGGER.debug("IP source for %s is %s", fritzbox_tools.host, local_ip)
            if portmap["NewInternalClient"] == local_ip:
                hass.add_job(
                    async_add_entities,
                    [
                        FritzBoxPortSwitch(
                            fritzbox_tools,
                            entry.title,
                            portmap,
                            i,
                            connection_type,
                        )
                    ],
                )

    def _create_profile_switches():
        _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_DEVICEPROFILE)
        if len(fritzbox_tools.fritz_profiles) > 0:
            for profile in fritzbox_tools.fritz_profiles.keys():
                hass.add_job(
                    async_add_entities,
                    [FritzBoxProfileSwitch(fritzbox_tools, entry.title, profile)],
                )

    def _create_wifi_switches():
        _LOGGER.debug("Setting up %s switches", SWITCH_TYPE_WIFINETWORK)

        std_table = {"ac": "5Ghz", "n": "2.4Ghz"}
        networks = {}
        for i in range(4):
            if ("WLANConfiguration" + str(i)) in fritzbox_tools.connection.services:
                network_info = service_call_action(
                    fritzbox_tools, "WLANConfiguration" + str(i), False, "GetInfo"
                )
                ssid = network_info["NewSSID"]
                if ssid in networks:
                    networks[i] = ssid + " " + std_table[network_info["NewStandard"]]
                else:
                    networks[i] = ssid

        for net in networks:
            hass.add_job(
                async_add_entities,
                [FritzBoxWifiSwitch(fritzbox_tools, entry.title, net, networks[net])],
            )

    hass.async_add_executor_job(_create_wifi_switches)
    hass.async_add_executor_job(_create_port_switches)
    hass.async_add_executor_job(_create_deflection_switches)
    hass.async_add_executor_job(_create_profile_switches)


class FritzBoxPortSwitch(FritzBoxBaseSwitch, SwitchEntity):
    """Defines a FRITZ!Box Tools PortForward switch."""

    def __init__(
        self,
        fritzbox_tools: FritzBoxTools,
        device_friendly_name,
        port_mapping,
        idx,
        connection_type,
    ):
        """Init Fritzbox port switch."""
        self.fritzbox_tools: FritzBoxTools = fritzbox_tools

        self._attributes = {}
        self.connection_type = connection_type
        self.port_mapping: dict = port_mapping  # dict in the format as it comes from fritzconnection. eg: {'NewRemoteHost': '0.0.0.0', 'NewExternalPort': 22, 'NewProtocol': 'TCP', 'NewInternalPort': 22, 'NewInternalClient': '192.168.178.31', 'NewEnabled': True, 'NewPortMappingDescription': 'Beast SSH ', 'NewLeaseDuration': 0}
        self._idx = idx  # needed for update routine

        switch_info = SwitchInfo(
            description=f'Port forward {port_mapping["NewPortMappingDescription"]}',
            friendly_name=device_friendly_name,
            icon="mdi:check-network",
            type=SWITCH_TYPE_PORTFORWARD,
            callback_update=self._async_fetch_update,
            callback_switch=self._async_handle_port_switch_on_off,
        )
        super().__init__(fritzbox_tools, switch_info)

    async def _async_fetch_update(self):
        """Fetch updates."""

        try:
            self.port_mapping = await self.hass.async_add_executor_job(
                lambda: self.fritzbox_tools.connection.call_action(
                    self.connection_type,
                    "GetGenericPortMappingEntry",
                    NewPortMappingIndex=self._idx,
                )
            )
            _LOGGER.debug(
                "Specific %s response: %s", SWITCH_TYPE_PORTFORWARD, self.port_mapping
            )
            self._attr_is_on = self.port_mapping["NewEnabled"] is True
            self._is_available = True

            self._attributes["internalIP"] = self.port_mapping["NewInternalClient"]
            self._attributes["internalPort"] = self.port_mapping["NewInternalPort"]
            self._attributes["externalPort"] = self.port_mapping["NewExternalPort"]
            self._attributes["protocol"] = self.port_mapping["NewProtocol"]
            self._attributes["description"] = self.port_mapping[
                "NewPortMappingDescription"
            ]
        except FritzConnectionException:
            _LOGGER.error(
                "Authorization Error: Please check the provided credentials and verify that you can log into the web interface"
            )
            self._is_available = False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Could not get %s state", self.name, exc_info=True)
            self._is_available = False

    async def _async_handle_port_switch_on_off(self, turn_on: bool) -> bool:

        self.port_mapping["NewEnabled"] = "1" if turn_on else "0"
        try:
            self.hass.async_add_executor_job(
                lambda: self.fritzbox_tools.connection.call_action(
                    self.connection_type, "AddPortMapping", **self.port_mapping
                )
            )
        except FritzSecurityError:
            _LOGGER.error(
                "Authorization Error: Please check the provided credentials and verify that you can log into the web interface",
                exc_info=True,
            )
        except FritzConnectionException:
            _LOGGER.error(
                "Home Assistant cannot call the wished service on the FRITZ!Box",
                exc_info=True,
            )
            return False

        return True


class FritzBoxDeflectionSwitch(FritzBoxBaseSwitch, SwitchEntity):
    """Defines a FRITZ!Box Tools PortForward switch."""

    def __init__(self, fritzbox_tools, device_friendly_name, dict_of_deflection):
        """Init Fritxbox Deflection class."""
        self.fritzbox_tools: FritzBoxTools = fritzbox_tools

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
        super().__init__(self.fritzbox_tools, switch_info)

    async def _async_fetch_update(self):
        """Fetch updates."""

        try:
            resp = await self.hass.async_add_executor_job(
                lambda: self.fritzbox_tools.connection.call_action(
                    "X_AVM-DE_OnTel:1", "GetDeflections"
                )
            )
            self.dict_of_deflection = xmltodict.parse(resp["NewDeflectionList"])[
                "List"
            ]["Item"]
            if isinstance(self.dict_of_deflection, list):
                self.dict_of_deflection = self.dict_of_deflection[self.id]

            _LOGGER.debug(
                "Specific %s response: NewDeflectionList=%s",
                SWITCH_TYPE_DEFLECTION,
                self.dict_of_deflection,
            )

            self._attr_is_on = self.dict_of_deflection["Enable"] == "1"
            self._is_available = True

            self._attributes["Type"] = self.dict_of_deflection["Type"]
            self._attributes["Number"] = self.dict_of_deflection["Number"]
            self._attributes["DeflectionToNumber"] = self.dict_of_deflection[
                "DeflectionToNumber"
            ]
            # Return mode sample: "eImmediately"
            self._attributes["Mode"] = self.dict_of_deflection["Mode"][1:]
            self._attributes["Outgoing"] = self.dict_of_deflection["Outgoing"]
            self._attributes["PhonebookID"] = self.dict_of_deflection["PhonebookID"]

        except FritzConnectionException:
            _LOGGER.error(
                "Authorization Error: Please check the provided credentials and verify that you can log into the web interface"
            )
            self._is_available = False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(
                "Could not get state of %s", SWITCH_TYPE_DEFLECTION, exc_info=True
            )
            self._is_available = False

    async def _async_switch_on_off_executor(self, turn_on: bool) -> None:
        """Handle deflection switch."""
        self.hass.async_add_executor_job(
            lambda: self.fritzbox_tools.connection.call_action(
                "X_AVM-DE_OnTel:1",
                "SetDeflectionEnable",
                NewDeflectionId=self.id,
                NewEnable="1" if turn_on else "0",
            )
        )


class FritzBoxProfileSwitch(FritzBoxBaseSwitch, SwitchEntity):
    """Defines a FRITZ!Box Tools DeviceProfile switch."""

    def __init__(self, fritzbox_tools, device_friendly_name, profile):
        """Init Fritz profile."""
        self.fritzbox_tools: FritzBoxTools = fritzbox_tools
        self.profile = profile

        switch_info = SwitchInfo(
            description=f"Profile {profile}",
            friendly_name=device_friendly_name,
            icon="mdi:router-wireless-settings",
            type=SWITCH_TYPE_DEVICEPROFILE,
            callback_update=self._async_fetch_update,
            callback_switch=self._async_switch_on_off_executor,
        )
        super().__init__(self.fritzbox_tools, switch_info)

    async def _async_fetch_update(self):
        """Update data."""
        try:
            status = await self.hass.async_add_executor_job(
                self.fritzbox_tools.fritz_profiles[self.profile].get_state
            )
            _LOGGER.debug(
                "Specific %s response: get_State()=%s",
                SWITCH_TYPE_DEVICEPROFILE,
                status,
            )
            if status == "never":
                self._attr_is_on = False
                self._is_available = True
            elif status == "unlimited":
                self._attr_is_on = True
                self._is_available = True
            else:
                self._is_available = False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Could not get %s state", self.name, exc_info=True)
            self._is_available = False

    async def _async_switch_on_off_executor(self, turn_on: bool) -> None:
        """Handle profile switch."""
        state = "unlimited" if turn_on else "never"
        await self.hass.async_add_executor_job(
            lambda: self.fritzbox_tools.fritz_profiles[self.profile].set_state(state)
        )


class FritzBoxWifiSwitch(FritzBoxBaseSwitch, SwitchEntity):
    """Defines a FRITZ!Box Tools Wifi switch."""

    def __init__(self, fritzbox_tools, device_friendly_name, network_num, network_name):
        """Init Fritz Wifi switch."""
        self._fritzbox_tools: FritzBoxTools = fritzbox_tools

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
        super().__init__(self._fritzbox_tools, switch_info)

    async def _async_fetch_update(self):
        """Fetch updates."""

        try:
            wifi_info = await self.hass.async_add_executor_job(
                lambda: self._fritzbox_tools.connection.call_action(
                    f"WLANConfiguration:{self._network_num}", "GetInfo"
                )
            )
            _LOGGER.debug(
                "Specific %s response: GetInfo=%s", SWITCH_TYPE_WIFINETWORK, wifi_info
            )

            self._attr_is_on = wifi_info["NewEnable"] is True
            self._is_available = True

            self._attributes["beacon_type"] = wifi_info["NewBeaconType"]
            self._attributes["BSSID"] = wifi_info["NewBSSID"]
            self._attributes["mac_address_control"] = wifi_info[
                "NewMACAddressControlEnabled"
            ]

        except FritzConnectionException:
            _LOGGER.error(
                "Authorization Error: Please check the provided credentials and verify that you can log into the web interface",
                exc_info=True,
            )
            self._is_available = False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Could not get %s state", self.name, exc_info=True)
            self._is_available = False

    async def _async_switch_on_off_executor(self, turn_on: bool) -> None:
        """Handle wifi switch."""
        self.hass.async_add_executor_job(
            lambda: self._fritzbox_tools.connection.call_action(
                f"WLANConfiguration{self._network_num}",
                "SetEnable",
                NewEnable="1" if turn_on else "0",
            )
        )
