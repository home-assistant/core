"""Support for ADS DateTime."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pyads
import voluptuous as vol

from homeassistant.components.datetime import (
    PLATFORM_SCHEMA as DATETIME_PLATFORM_SCHEMA,
    DateTimeEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .. import ads
from . import AdsEntity

SCAN_INTERVAL = timedelta(seconds=3)
DEFAULT_NAME = "ADS DateTime"

CONF_ADS_VAR = "adsvar"

PLATFORM_SCHEMA = DATETIME_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the DateTime platform for ADS."""

    ads_hub = hass.data.get(ads.DATA_ADS)
    ads_var = config.get(CONF_ADS_VAR)
    name = config[CONF_NAME]

    add_entities(
        [
            AdsDateTime(
                ads_hub,
                ads_var,
                name,
            )
        ]
    )


class AdsDateTime(AdsEntity, DateTimeEntity):
    """Representation of ADS DateTime entity."""

    def __init__(self, ads_hub, ads_var, name):
        """Initialize AdsDateTime entity."""
        super().__init__(ads_hub, name, ads_var)
        self._datetime = None

    async def async_added_to_hass(self) -> None:
        """Register device notification."""

        if self._ads_var is not None:
            await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_DT)
        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self) -> bool:
        """Return True if the entity should be polled."""
        return True

    async def async_set_value(self, value: datetime) -> None:
        """Set the date/time."""
        new_datetime = value
        await self.hass.async_add_executor_job(self._write_value, new_datetime)
        self._datetime = new_datetime
        self._attr_native_value = new_datetime
        self.async_write_ha_state()

    def _write_value(self, dt_value: datetime) -> None:
        # Convert Python datetime to epoch time (seconds since 1970-01-01)
        epoch_time = int(dt_value.timestamp())
        # Write the epoch time to the PLC as an integer
        self._ads_hub.write_by_name(self._ads_var, epoch_time, pyads.PLCTYPE_DT)

    async def async_update(self) -> None:
        """Retrieve the latest state from the ADS device."""
        epoch_value = self._ads_hub.read_by_name(self._ads_var, pyads.PLCTYPE_DT)
        self._datetime = datetime.fromtimestamp(epoch_value, tz=UTC)
        self._attr_native_value = self._datetime
        self.async_write_ha_state()
