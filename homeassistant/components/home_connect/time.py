"""Provides time enties for Home Connect."""

from collections.abc import Callable
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

    def get_entities_for_appliance(
        appliance: HomeConnectApplianceData,
    ) -> list[HomeConnectTimeEntity]:
        """Get a list of entities."""
        remove_listener: Callable[[], None] | None = None

        def handle_removed_device() -> None:
            """Handle removed device."""
            for entity_unique_id in added_entities.copy():
                if entity_unique_id and appliance.info.ha_id in entity_unique_id:
                    added_entities.remove(entity_unique_id)
            assert remove_listener
            remove_listener()

        remove_listener = entry.runtime_data.async_add_listener(
            handle_removed_device,
            (appliance.info.ha_id, EventKey.BSH_COMMON_APPLIANCE_DEPAIRED),
        )
        entry.async_on_unload(remove_listener)

        return [
            HomeConnectTimeEntity(entry.runtime_data, appliance, description)
            for description in TIME_ENTITIES
            if description.key in appliance.settings
        ]

    entities = [
        entity
        for appliance in entry.runtime_data.data.values()
        for entity in get_entities_for_appliance(appliance)
    ]
    async_add_entities(entities)

    added_entities = {entity.unique_id for entity in entities}

    def handle_paired_or_connected_device() -> None:
        """Handle new paired device or a device that has been connected."""
        for appliance in entry.runtime_data.data.values():
            new_entities = [
                entity
                for entity in get_entities_for_appliance(appliance)
                if entity.unique_id not in added_entities
            ]
            async_add_entities(new_entities)
            added_entities.update(entity.unique_id for entity in new_entities)

    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(handle_paired_or_connected_device)
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
