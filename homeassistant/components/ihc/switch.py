"""Support for IHC switches."""
import logging
from typing import Any

from ihcsdk.ihccontroller import IHCController

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_OFF_ID, CONF_ON_ID, DOMAIN, IHC_CONTROLLER
from .ihcdevice import IHCDevice
from .util import async_pulse, async_set_bool

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load IHC switches based on a config entry."""
    controller_id: str = str(config_entry.unique_id)
    controller_data = hass.data[DOMAIN][controller_id]
    ihc_controller: IHCController = controller_data[IHC_CONTROLLER]
    switches = []
    if "switch" in controller_data and controller_data["switch"]:
        for name, device in controller_data["switch"].items():
            ihc_id = device["ihc_id"]
            product_cfg = device["product_cfg"]
            product = device["product"]
            ihc_off_id = product_cfg.get(CONF_OFF_ID)
            ihc_on_id = product_cfg.get(CONF_ON_ID)
            switch = IHCSwitch(
                ihc_controller,
                controller_id,
                name,
                ihc_id,
                ihc_off_id,
                ihc_on_id,
                product,
            )
            switches.append(switch)
        async_add_entities(switches)


class IHCSwitch(IHCDevice, SwitchEntity):
    """Representation of an IHC switch."""

    def __init__(
        self,
        ihc_controller: IHCController,
        controller_id: str,
        name: str,
        ihc_id: int,
        ihc_off_id: int,
        ihc_on_id: int,
        product=None,
    ) -> None:
        """Initialize the IHC switch."""
        super().__init__(ihc_controller, controller_id, name, ihc_id, product)
        self._ihc_off_id = ihc_off_id
        self._ihc_on_id = ihc_on_id

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if self._ihc_on_id:
            await async_pulse(self.hass, self.ihc_controller, self._ihc_on_id)
        else:
            await async_set_bool(self.hass, self.ihc_controller, self.ihc_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self._ihc_off_id:
            await async_pulse(self.hass, self.ihc_controller, self._ihc_off_id)
        else:
            await async_set_bool(self.hass, self.ihc_controller, self.ihc_id, False)

    def on_ihc_change(self, ihc_id, value):
        """Handle IHC resource change."""
        self._attr_is_on = value
        self.schedule_update_ha_state()
