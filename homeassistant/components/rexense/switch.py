"""Switches connected to a Rexense gateway."""

from typing import Any, override

from aiorexense import Endpoint, RexenseError, RexenseGateway

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RexenseConfigEntry
from .const import DOMAIN, MANUFACTURER

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RexenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches with confirmed writable on/off capabilities."""
    gateway = entry.runtime_data.gateway
    async_add_entities(
        RexenseSwitch(gateway, endpoint, entry.runtime_data.gateway_device_id)
        for endpoint in gateway.endpoints.values()
        if endpoint.dev_type == "switch"
        and endpoint.confirmed
        and endpoint.writable("on")
        and endpoint.members("properties")["on"]["type"] == "bool"
    )


class RexenseSwitch(SwitchEntity):
    """An on/off endpoint whose state is reported by the gateway."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "endpoint"

    def __init__(
        self, gateway: RexenseGateway, endpoint: Endpoint, gateway_device_id: str
    ) -> None:
        """Initialize the endpoint's stable identity and device information."""
        self._gateway = gateway
        self._address = endpoint.addr
        self._attr_unique_id = f"{gateway.unique_id}_{endpoint.addr}_on"
        self._attr_translation_placeholders = {
            "endpoint": endpoint.addr.rsplit(":", 1)[1]
        }
        if alias := endpoint.metadata.get("lalias"):
            self._attr_name = alias
        node = endpoint.node
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{gateway.unique_id}_{endpoint.mac}")},
            via_device_id=gateway_device_id,
            name=node.get("model_id") or endpoint.mac,
            manufacturer=node.get("mfg_name") or MANUFACTURER,
            model=node.get("model_id"),
            sw_version=node.get("sw_build_id"),
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe only while the entity is registered in Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(self._gateway.subscribe(self.async_write_ha_state))

    @property
    @override
    def available(self) -> bool:
        """Return whether both the gateway and endpoint are online."""
        return (
            self._gateway.connected
            and (endpoint := self._gateway.endpoints.get(self._address)) is not None
            and endpoint.state == "online"
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the observed state, retaining unknown when no value is reported."""
        if endpoint := self._gateway.endpoints.get(self._address):
            value = endpoint.properties.get("on")
            return value if isinstance(value, bool) else None
        return None

    async def _async_set(self, value: bool) -> None:
        """Map a library failure to a Home Assistant action error."""
        try:
            await self._gateway.async_execute(self._address, {"on": value})
        except RexenseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set(False)
