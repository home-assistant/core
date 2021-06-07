"""Support for tracking MySensors devices."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.components import mysensors
from homeassistant.components.device_tracker import DOMAIN
from homeassistant.components.mysensors import DevId
from homeassistant.components.mysensors.const import (
    ATTR_GATEWAY_ID,
    DiscoveryInfo,
    GatewayId,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify

from .helpers import on_unload


async def async_setup_scanner(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_see: Callable,
    discovery_info: DiscoveryInfo | None = None,
) -> bool:
    """Set up the MySensors device scanner."""
    if not discovery_info:
        return False

    new_devices = mysensors.setup_mysensors_platform(
        hass,
        DOMAIN,
        discovery_info,
        MySensorsDeviceScanner,
        device_args=(hass, async_see),
    )
    if not new_devices:
        return False

    for device in new_devices:
        gateway_id: GatewayId = discovery_info[ATTR_GATEWAY_ID]
        dev_id: DevId = (gateway_id, device.node_id, device.child_id, device.value_type)
        on_unload(
            hass,
            gateway_id,
            async_dispatcher_connect(
                hass,
                mysensors.const.CHILD_CALLBACK.format(*dev_id),
                device.async_update_callback,
            ),
        )
        on_unload(
            hass,
            gateway_id,
            async_dispatcher_connect(
                hass,
                mysensors.const.NODE_CALLBACK.format(gateway_id, device.node_id),
                device.async_update_callback,
            ),
        )

    return True


class MySensorsDeviceScanner(mysensors.device.MySensorsDevice):
    """Represent a MySensors scanner."""

    def __init__(self, hass: HomeAssistant, async_see: Callable, *args: Any) -> None:
        """Set up instance."""
        super().__init__(*args)
        self.async_see = async_see
        self.hass = hass

    async def _async_update_callback(self) -> None:
        """Update the device."""
        await self.async_update()
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        position = child.values[self.value_type]
        latitude, longitude, _ = position.split(",")

        await self.async_see(
            dev_id=slugify(self.name),
            host_name=self.name,
            gps=(latitude, longitude),
            battery=node.battery_level,
            attributes=self._extra_attributes,
        )
