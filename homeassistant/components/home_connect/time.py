"""Provides time enties for Home Connect."""

from datetime import time
from typing import cast

from aiohomeconnect.model import SettingKey
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import setup_home_connect_entry
from .const import (
    DOMAIN,
    SVE_TRANSLATION_KEY_SET_SETTING,
    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID,
    SVE_TRANSLATION_PLACEHOLDER_KEY,
    SVE_TRANSLATION_PLACEHOLDER_VALUE,
)
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
from .entity import HomeConnectEntity
from .utils import get_dict_from_home_connect_error

PARALLEL_UPDATES = 1

TIME_ENTITIES = (
    TimeEntityDescription(
        key=SettingKey.BSH_COMMON_ALARM_CLOCK,
        translation_key="alarm_clock",
    ),
)


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return [
        HomeConnectTimeEntity(entry.runtime_data, appliance, description)
        for description in TIME_ENTITIES
        if description.key in appliance.settings
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""
    setup_home_connect_entry(
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


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
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey(self.bsh_key),
                value=time_to_seconds(value),
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=SVE_TRANSLATION_KEY_SET_SETTING,
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                    SVE_TRANSLATION_PLACEHOLDER_KEY: self.bsh_key,
                    SVE_TRANSLATION_PLACEHOLDER_VALUE: str(value),
                },
            ) from err

    def update_native_value(self) -> None:
        """Set the value of the entity."""
        data = self.appliance.settings[cast(SettingKey, self.bsh_key)]
        self._attr_native_value = seconds_to_time(data.value)
