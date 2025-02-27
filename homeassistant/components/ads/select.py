"""Support for ADS select entities."""

from __future__ import annotations

import pyads
import voluptuous as vol

from homeassistant.components.select import (
    PLATFORM_SCHEMA as SELECT_PLATFORM_SCHEMA,
    SelectEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ADS_HUB, CONF_ADS_HUB_DEFAULT, DOMAIN, AdsSelectKeys
from .entity import AdsEntity
from .hub import AdsHub

PLATFORM_SCHEMA = SELECT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_HUB, default=CONF_ADS_HUB_DEFAULT): cv.string,
        vol.Required(AdsSelectKeys.VAR): cv.string,
        vol.Optional(AdsSelectKeys.NAME, default=AdsSelectKeys.DEFAULT_NAME): cv.string,
        vol.Required(AdsSelectKeys.OPTIONS): vol.All(cv.ensure_list, [cv.string]),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an ADS select device."""

    hub_name: str = config[CONF_ADS_HUB]
    hub_key = f"{DOMAIN}_{hub_name}"
    ads_hub = hass.data.get(hub_key)
    if not ads_hub:
        return

    ads_var: str = config[AdsSelectKeys.VAR]
    name: str = config[AdsSelectKeys.NAME]
    options: list[str] = config[AdsSelectKeys.OPTIONS]
    entity = AdsSelect(ads_hub, ads_var, name, options)
    add_entities([entity])


class AdsSelect(AdsEntity, SelectEntity):
    """Representation of an ADS select entity."""

    def __init__(
        self,
        ads_hub: AdsHub,
        ads_var: str,
        name: str,
        options: list[str],
    ) -> None:
        """Initialize the AdsSelect entity."""
        super().__init__(ads_hub, name, ads_var)
        self._attr_options = options
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_INT)
        self._ads_hub.add_device_notification(
            self._ads_var, pyads.PLCTYPE_INT, self._handle_ads_value
        )

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        if option in self._attr_options:
            index = self._attr_options.index(option)
            self._ads_hub.write_by_name(self._ads_var, index, pyads.PLCTYPE_INT)
            self._attr_current_option = option

    def _handle_ads_value(self, name: str, value: int) -> None:
        """Handle the value update from ADS."""
        if 0 <= value < len(self._attr_options):
            self._attr_current_option = self._attr_options[value]
            self.schedule_update_ha_state()
