"""Support for Freebox Delta, Revolution and Mini 4K."""
from __future__ import annotations

import logging
from typing import Any

from freebox_api.exceptions import InsufficientPermissionsError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the switch."""
    router = hass.data[DOMAIN][entry.unique_id]

    entities = []

    entities.append(FreeboxWifiSwitch(router))

    _LOGGER.info(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )

    for home_node in router.home_nodes.values():
        if home_node["category"] != "shutter":
            for endpoint in home_node.get("show_endpoints"):
                if endpoint["ep_type"] == "slot" and endpoint["value_type"] == "bool":
                    entities.append(
                        FreeboxHomeNodeSwitch(
                            router,
                            home_node,
                            endpoint,
                            endpoint["name"],
                        )
                    )

    async_add_entities(entities, True)


class FreeboxSwitch(SwitchEntity):
    """Representation of a Freebox switch."""

    _attr_should_poll = False

    def __init__(
        self,
        router: FreeboxRouter,
        endpoint_name: str,
        unik: Any,
    ) -> None:
        """Initialize a Freebox binary_sensors."""
        self.entity_description = SwitchEntityDescription(
            key="switch", name=endpoint_name
        )
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {endpoint_name} {unik}"

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox binary_sensors."""
        # state = self._router.sensors[self.entity_description.key]
        # self._attr_is_on = state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._router.device_info

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_sensor_update,
                self.async_on_demand_update,
            )
        )


class FreeboxHomeNodeSwitch(FreeboxSwitch):
    """Representation of a Freebox Home node switch."""

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        endpoint: dict[str, Any],
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize a Freebox Home node switch."""
        super().__init__(router, description, f"{home_node['id']} {endpoint['id']}")
        self._home_node = home_node
        self._endpoint = endpoint
        self._attr_name = f"{home_node['label']} {endpoint['name']}"
        self._unique_id = f"{self._router.mac} {endpoint['name']} {self._home_node['id']} {endpoint['id']}"
        self._enabled = None
        self._get_endpoint_id = None

        # Discover for get endpoint
        for endpoint_candidate in home_node.get("show_endpoints"):
            if (
                endpoint_candidate["name"] == endpoint["name"]
                and endpoint_candidate["ep_type"] == "signal"
            ):
                self._get_endpoint_id = endpoint_candidate["id"]
                break

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        fw_version = None
        if "props" in self._home_node:
            props = self._home_node["props"]
            if "FwVersion" in props:
                fw_version = props["FwVersion"]

        return DeviceInfo(
            identifiers={(DOMAIN, self._home_node["id"])},
            model=f'{self._home_node["category"]}',
            name=f"{self._home_node['label']}",
            sw_version=fw_version,
            via_device=(
                DOMAIN,
                self._router.mac,
            ),
            vendor_name="Freebox SAS",
            manufacturer="Freebox SAS",
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._enabled

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox Home node switch."""
        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if self._get_endpoint_id == end_point["id"]:
                    self._enabled = end_point["value"]
                    break
        self._attr_is_on = self._enabled

    async def _async_set_state(self, enabled: bool):
        """Turn the switch on or off."""
        value_enabled = {"value": enabled}
        try:
            await self._router.api.home.set_home_endpoint_value(
                self._home_node["id"], self._endpoint["id"], value_enabled
            )
            self._enabled = enabled
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings. Please refer to documentation"
            )

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._async_set_state(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._async_set_state(False)
        self.async_write_ha_state()

    async def async_update(self):
        """Get switch status and update it."""
        try:
            ret = await self._router.api.home.get_home_endpoint_value(
                self._home_node["id"], self._get_endpoint_id
            )
            self._enabled = ret["value"]
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings. Please refer to documentation"
            )
        return self._enabled


class FreeboxWifiSwitch(SwitchEntity):
    """Representation of a freebox wifi switch."""

    def __init__(self, router: FreeboxRouter) -> None:
        """Initialize the Wifi switch."""
        self._name = "Freebox WiFi"
        self._state = None
        self._router = router
        self._unique_id = f"{self._router.mac} {self._name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._router.device_info

    async def _async_set_state(self, enabled: bool):
        """Turn the switch on or off."""
        wifi_config = {"enabled": enabled}
        try:
            await self._router.wifi.set_global_config(wifi_config)
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings. Please refer to documentation"
            )

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._async_set_state(False)

    async def async_update(self):
        """Get the state and update it."""
        datas = await self._router.wifi.get_global_config()
        active = datas["enabled"]
        self._state = bool(active)
