"""Provides time enties for Home Connect."""

from datetime import time
from typing import cast

from aiohomeconnect.model import EventKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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

TIME_ENTITIES = (
    TimeEntityDescription(
        key=SettingKey.BSH_COMMON_ALARM_CLOCK,
        translation_key="alarm_clock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""
    known_enitiy_unique_ids: dict[str, str] = {}

    def get_entities_for_appliance(
        appliance: HomeConnectApplianceData,
    ) -> list[HomeConnectTimeEntity]:
        """Get a list of entities."""
        return [
            HomeConnectTimeEntity(entry.runtime_data, appliance, description)
            for description in TIME_ENTITIES
            if description.key in appliance.settings
        ]

    for appliance in entry.runtime_data.data.values():
        entities = get_entities_for_appliance(appliance)
        known_enitiy_unique_ids.update(
            {cast(str, entity.unique_id): appliance.info.ha_id for entity in entities}
        )
        async_add_entities(entities)

    def handle_paired_or_connected_appliance() -> None:
        """Handle new paired appliance or a appliance that has been connected."""
        for appliance in entry.runtime_data.data.values():
            entities_to_add = [
                entity
                for entity in get_entities_for_appliance(appliance)
                if cast(str, entity.unique_id) not in known_enitiy_unique_ids
            ]
            known_enitiy_unique_ids.update(
                {
                    cast(str, entity.unique_id): appliance.info.ha_id
                    for entity in entities_to_add
                }
            )
            async_add_entities(entities_to_add)

    def handle_depaired_appliance() -> None:
        """Handle removed appliance."""
        for entity_unique_id, appliance_id in known_enitiy_unique_ids.copy().items():
            if appliance_id not in entry.runtime_data.data:
                known_enitiy_unique_ids.pop(entity_unique_id, None)

    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(
            handle_paired_or_connected_appliance,
            (
                EventKey.BSH_COMMON_APPLIANCE_PAIRED,
                EventKey.BSH_COMMON_APPLIANCE_CONNECTED,
            ),
        )
    )
    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(
            handle_depaired_appliance,
            (EventKey.BSH_COMMON_APPLIANCE_DEPAIRED,),
        ),
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
