"""Support for IHC event entities."""

from __future__ import annotations

from ihcsdk.ihccontroller import IHCController

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, IHC_CONTROLLER
from .entity import IHCEntity


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the IHC event platform."""
    if discovery_info is None:
        return
    devices = []
    for name, device in discovery_info.items():
        ihc_id = device["ihc_id"]
        product = device["product"]
        controller_id = device["ctrl_id"]
        ihc_controller: IHCController = hass.data[DOMAIN][controller_id][IHC_CONTROLLER]
        devices.append(
            IHCButtonEventEntity(ihc_controller, controller_id, name, ihc_id, product)
        )
    add_entities(devices)


class IHCButtonEventEntity(IHCEntity, EventEntity):
    """IHC Event Entity for wireless battery-powered push buttons.

    The associated IHC resource is a boolean airlink_input that momentarily
    goes True when a button is pressed. A 'pressed' event is fired on each press.
    """

    _attr_event_types = ["pressed"]
    _attr_icon = "mdi:light-switch"

    def __init__(
        self,
        ihc_controller: IHCController,
        controller_id: str,
        name: str,
        ihc_id: int,
        product=None,
    ) -> None:
        """Initialize the IHC button event entity."""
        super().__init__(ihc_controller, controller_id, name, ihc_id, product)
        if product:
            channel = product.get("address_channel")
            if channel is not None:
                self._name = f"{product['group']}_{product['id']}_{channel:02d}"

    @callback
    def _handle_press(self) -> None:
        """Handle a button press on the Home Assistant event loop."""
        self._trigger_event("pressed", self.extra_state_attributes or None)
        self.async_write_ha_state()

    def on_ihc_change(self, _ihc_id: int, value: bool) -> None:
        """IHC resource has changed."""
        if value:
            self.hass.add_job(self._handle_press)
