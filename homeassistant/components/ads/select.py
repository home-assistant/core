"""Support for ADS select."""

from __future__ import annotations

from datetime import timedelta

import pyads
import voluptuous as vol

from homeassistant.components.select import (
    PLATFORM_SCHEMA as SELECT_PLATFORM_SCHEMA,
    SelectEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .. import ads
from . import AdsEntity

SCAN_INTERVAL = timedelta(seconds=3)
DEFAULT_NAME = "ADS Select"

CONF_ADS_VAR = "adsvar"
CONF_ADS_VAR_OPTIONS = "adsvar_options"


PLATFORM_SCHEMA = SELECT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_VAR): cv.string,
        vol.Optional(
            CONF_ADS_VAR_OPTIONS, default=[]
        ): cv.ensure_list,  # Ensure options are a list
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the select platform for ADS."""

    ads_hub = hass.data.get(ads.DATA_ADS)
    ads_var = config.get(CONF_ADS_VAR)
    ads_var_options = config.get(CONF_ADS_VAR_OPTIONS)  # Load options from config
    name = config[CONF_NAME]

    add_entities(
        [
            AdsSelect(
                ads_hub,
                ads_var,
                ads_var_options,
                name,
            )
        ]
    )


class AdsSelect(AdsEntity, SelectEntity):
    """Representation of ADS select entity."""

    def __init__(
        self,
        ads_hub,
        ads_var,
        ads_var_options,
        name,
    ):
        """Initialize AdsSelect entity."""
        super().__init__(ads_hub, name, ads_var)
        self._options = ads_var_options
        self._selected_option = None
        self._option_map = {option: idx for idx, option in enumerate(ads_var_options)}

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_STRING)
        self.async_schedule_update_ha_state(True)

    def _write_value(self, index: int) -> None:
        """Write the selected value to the PLC."""
        # Convert the value to the required format if necessary
        self._ads_hub.write_by_name(self._ads_var, index, pyads.PLCTYPE_INT)

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        return self._options

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._selected_option

    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        if option in self._options:
            index = self._option_map[option]
            await self.hass.async_add_executor_job(self._write_value, index)
            self._selected_option = option
            self.async_write_ha_state()
