"""Support for ADS select entities."""

from typing import override

import probatio
import pyads

from homeassistant.components.select import (
    PLATFORM_SCHEMA as SELECT_PLATFORM_SCHEMA,
    SelectEntity,
)
from homeassistant.const import CONF_NAME, CONF_OPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ADS_VAR, STATE_KEY_STATE
from .entity import AdsEntity
from .hub import AdsHub, async_get_hub

DEFAULT_NAME = "ADS select"

PLATFORM_SCHEMA = SELECT_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_ADS_VAR): cv.string,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Required(CONF_OPTIONS): probatio.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an ADS select device."""
    ads_hub = async_get_hub(hass)

    ads_var: str = config[CONF_ADS_VAR]
    name: str = config[CONF_NAME]
    options: list[str] = config[CONF_OPTIONS]

    entity = AdsSelect(ads_hub, ads_var, name, options)

    async_add_entities([entity])


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

    @override
    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_INT)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the option the PLC reports."""
        index = self._state_dict[STATE_KEY_STATE]
        if index is None or not 0 <= index < len(self._attr_options):
            return None
        return self._attr_options[index]

    @override
    def select_option(self, option: str) -> None:
        """Change the selected option."""
        index = self._attr_options.index(option)
        self._ads_hub.write_by_name(self._ads_var, index, pyads.PLCTYPE_INT)
