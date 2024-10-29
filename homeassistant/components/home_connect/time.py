"""Provides time enties for Home Connect."""

from datetime import time
import logging

from homeconnect.api import HomeConnectError

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_dict_from_home_connect_error
from .api import ConfigEntryAuth
from .const import (
    ATTR_VALUE,
    DOMAIN,
    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID,
    SVE_TRANSLATION_PLACEHOLDER_SETTING_KEY,
    SVE_TRANSLATION_PLACEHOLDER_VALUE,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


TIME_ENTITIES = (
    TimeEntityDescription(
        key="BSH.Common.Setting.AlarmClock",
        translation_key="alarm_clock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities() -> list[HomeConnectTimeEntity]:
        """Get a list of entities."""
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        return [
            HomeConnectTimeEntity(device, description)
            for description in TIME_ENTITIES
            for device in hc_api.devices
            if description.key in device.appliance.status
        ]

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


def seconds_to_time(seconds: int) -> time:
    """Convert seconds to a time object."""
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return time(hour=hours, minute=minutes, second=sec)


def time_to_seconds(t: time) -> int:
    """Convert a time object to seconds."""
    return t.hour * 3600 + t.minute * 60 + t.second


class HomeConnectTimeEntity(HomeConnectEntity, TimeEntity):
    """Time setting class for Home Connect."""

    async def async_set_value(self, value: time) -> None:
        """Set the native value of the entity."""
        _LOGGER.debug(
            "Tried to set value %s to %s for %s",
            value,
            self.bsh_key,
            self.entity_id,
        )
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting,
                self.bsh_key,
                time_to_seconds(value),
            )
        except HomeConnectError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_setting",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                    SVE_TRANSLATION_PLACEHOLDER_SETTING_KEY: self.bsh_key,
                    SVE_TRANSLATION_PLACEHOLDER_VALUE: str(value),
                },
            ) from err

    async def async_update(self) -> None:
        """Update the Time setting status."""
        data = self.device.appliance.status.get(self.bsh_key)
        if data is None:
            _LOGGER.error("No value for %s", self.bsh_key)
            self._attr_native_value = None
            return
        seconds = data.get(ATTR_VALUE, None)
        if seconds is not None:
            self._attr_native_value = seconds_to_time(seconds)
        else:
            self._attr_native_value = None
        _LOGGER.debug("Updated, new value: %s", self._attr_native_value)
