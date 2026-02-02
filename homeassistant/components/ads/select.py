"""Support for ADS select entities."""

from __future__ import annotations

import pyads
import voluptuous as vol

from homeassistant.components.select import (
    PLATFORM_SCHEMA as SELECT_PLATFORM_SCHEMA,
    SelectEntity,
)
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ADS_VAR, DATA_ADS
from .entity import AdsEntity
from .hub import AdsHub

DEFAULT_NAME = "ADS select"

CONF_OPTIONS = "options"

PLATFORM_SCHEMA = SELECT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_OPTIONS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an ADS select device."""
    ads_hub = hass.data[DATA_ADS]

    ads_var: str = config[CONF_ADS_VAR]
    name: str = config[CONF_NAME]
    options: list[str] = config[CONF_OPTIONS]
    unique_id: str | None = config.get(CONF_UNIQUE_ID)

    entity = AdsSelect(ads_hub, ads_var, name, options, unique_id)

    add_entities([entity])


class AdsSelect(AdsEntity, SelectEntity):
    """Representation of an ADS select entity."""

    def __init__(
        self,
        ads_hub: AdsHub,
        ads_var: str,
        name: str,
        options: list[str],
        unique_id: str | None,
    ) -> None:
        """Initialize the AdsSelect entity."""
        super().__init__(ads_hub, name, ads_var, unique_id)
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
