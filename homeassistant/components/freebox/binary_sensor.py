"""Support for Freebox binary_sensor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, HOME_NODES_BINARY_SENSORS
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the binary_sensors."""
    router = hass.data[DOMAIN][entry.unique_id]
    entities = []

    _LOGGER.debug(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )

    for home_node in router.home_nodes.values():
        for endpoint in home_node.get("show_endpoints"):
            if endpoint["ep_type"] == "signal":
                if endpoint["name"] == "cover":
                    entities.append(
                        FreeboxHomeNodeBinarySensor(
                            router,
                            home_node,
                            endpoint,
                            HOME_NODES_BINARY_SENSORS[endpoint["name"]],
                        )
                    )
                elif endpoint["name"] == "trigger":
                    if home_node["category"] == "pir":
                        entities.append(
                            FreeboxHomeNodeBinarySensor(
                                router,
                                home_node,
                                endpoint,
                                HOME_NODES_BINARY_SENSORS["motion"],
                            )
                        )
                    elif home_node["category"] == "dws":
                        entities.append(
                            FreeboxHomeNodeBinarySensor(
                                router,
                                home_node,
                                endpoint,
                                HOME_NODES_BINARY_SENSORS["opening"],
                            )
                        )

    async_add_entities(entities, True)


class FreeboxBinarySensor(BinarySensorEntity):
    """Representation of a Freebox binary_sensors."""

    _attr_should_poll = False

    def __init__(
        self,
        router: FreeboxRouter,
        description: BinarySensorEntityDescription,
        unik: Any,
    ) -> None:
        """Initialize a Freebox binary_sensor."""
        self.entity_description = description
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {description.name} {unik}"

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox binary_sensor."""
        state = self._router.sensors[self.entity_description.key]
        self._attr_is_on = state

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


class FreeboxHomeNodeBinarySensor(FreeboxBinarySensor):
    """Representation of a Freebox Home node binary_sensor."""

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        endpoint: dict[str, Any],
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize a Freebox Home node binary_sensor."""
        super().__init__(router, description, f"{home_node['id']} {endpoint['id']}")
        self._home_node = home_node
        self._endpoint = endpoint
        self._attr_name = f"{home_node['label']} {description.name}"
        self._unique_id = f"{self._router.mac} {description.key} {self._home_node['id']} {endpoint['id']}"

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

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox Home node binary_sensor."""
        value = None

        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if self._endpoint["id"] == end_point["id"]:
                    value = (
                        not end_point["value"]
                        if end_point["name"] == "trigger"
                        else end_point["value"]
                    )
                    break

        self._attr_is_on = value
