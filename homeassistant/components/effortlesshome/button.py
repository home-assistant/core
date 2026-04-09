from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from .const import DOMAIN, NAME

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    async_add_entities([DeployLatestConfigButton(hass, entry)])

class DeployLatestConfigButton(ButtonEntity):
    _attr_name = "Deploy Latest EffortlessHome Config"

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self._attr_unique_id = f"deploy_latest_effortlesshome_config_button_{entry.entry_id}"
        self._attr_config_entry_id = entry.entry_id


    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
            "model": NAME,
        }

    async def async_press(self) -> None:
        from . import deploy_latest_config
        _LOGGER.info("[EffortlessHome] Button pressed: Deploying latest config...")
        await deploy_latest_config(self.hass)
