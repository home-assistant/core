import logging
from typing import Any, Mapping

from ndms2_client import InterfaceInfo

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, ROUTER
from .router import KeeneticRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up interfaces for Keenetic NDMS2 component."""
    router: KeeneticRouter = hass.data[DOMAIN][config_entry.entry_id][ROUTER]

    tracked: set[str] = set()

    @callback
    def update_from_router():
        """Update the status of devices."""
        update_items(router, async_add_entities, tracked)

    async_dispatcher_connect(hass, router.signal_update, update_from_router)

    update_from_router()


@callback
def update_items(router: KeeneticRouter, async_add_entities, tracked: set[str]):
    """Update tracked interface state from the hub."""
    new_tracked: list[KeeneticInterface] = []
    for name, interface in router.last_interfaces.items():
        if name not in tracked:
            tracked.add(name)
            new_tracked.append(KeeneticInterface(router, interface))

    async_add_entities(new_tracked)


class KeeneticInterface(SwitchEntity):
    """Representation of network interface."""
    _is_available: bool
    _router: KeeneticRouter
    _interface_info: InterfaceInfo

    _attr_has_entity_name = True
    _attr_should_poll = False
    _entity_component_unrecorded_attributes: frozenset[str] = {'description', 'mac', 'mask', 'mtu', 'security_level',
                                                               'type', 'uptime', 'ssid', 'plugged'}

    def __init__(self, router: KeeneticRouter, interface_info: InterfaceInfo) -> None:
        self._router = router
        self._interface_info = interface_info
        self._attr_unique_id = f"interface_{interface_info.name}_{router.config_entry.entry_id}"
        self._is_available = True

    @property
    def device_class(self) -> SwitchDeviceClass:
        return SwitchDeviceClass.SWITCH

    @property
    def name(self) -> str:
        return self._interface_info.description or self._interface_info.name

    @property
    def available(self) -> bool:
        return self._is_available

    @property
    def is_on(self) -> bool | None:
        return self._interface_info.state == "up"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._router.set_interface_state(self._interface_info.name, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._router.set_interface_state(self._interface_info.name, False)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return {
            'link': self._interface_info.link,
            'state': self._interface_info.state,
            'address': self._interface_info.address,
            'description': self._interface_info.description,
            'connected': self._interface_info.connected,
            'mac': self._interface_info.mac,
            'mask': self._interface_info.mask,
            'mtu': self._interface_info.mtu,
            'security_level': self._interface_info.security_level,
            'type': self._interface_info.type,
            'uptime': self._interface_info.uptime,
            'ssid': self._interface_info.ssid,
            'plugged': self._interface_info.plugged
        }

    async def async_added_to_hass(self) -> None:
        """Interface entity created."""
        _LOGGER.debug("New interface %s (%s)", self.name, self.unique_id)

        @callback
        async def update_device() -> None:
            _LOGGER.debug(
                "Updating Keenetic interface %s (%s)",
                self.entity_id,
                self.unique_id,
            )
            new_interface_info = self._router.last_interfaces.get(self._interface_info.name)
            if new_interface_info:
                self._interface_info = new_interface_info
                self._is_available = True
            else:
                self._is_available = False
                await self.async_remove()

            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._router.signal_update, update_device
            )
        )
