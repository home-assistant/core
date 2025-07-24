"""Provides time entities for Home Connect."""

from datetime import time
from typing import cast

from aiohomeconnect.model import SettingKey
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .common import setup_home_connect_entry
from .const import DOMAIN
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
from .entity import HomeConnectEntity
from .utils import get_dict_from_home_connect_error

PARALLEL_UPDATES = 1

TIME_ENTITIES = (
    TimeEntityDescription(
        key=SettingKey.BSH_COMMON_ALARM_CLOCK,
        translation_key="alarm_clock",
        entity_registry_enabled_default=False,
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

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        if self.bsh_key is SettingKey.BSH_COMMON_ALARM_CLOCK:
            automations = automations_with_entity(self.hass, self.entity_id)
            scripts = scripts_with_entity(self.hass, self.entity_id)
            items = automations + scripts
            if not items:
                return

            entity_reg: er.EntityRegistry = er.async_get(self.hass)
            entity_automations = [
                automation_entity
                for automation_id in automations
                if (automation_entity := entity_reg.async_get(automation_id))
            ]
            entity_scripts = [
                script_entity
                for script_id in scripts
                if (script_entity := entity_reg.async_get(script_id))
            ]

            items_list = [
                f"- [{item.original_name}](/config/automation/edit/{item.unique_id})"
                for item in entity_automations
            ] + [
                f"- [{item.original_name}](/config/script/edit/{item.unique_id})"
                for item in entity_scripts
            ]

            async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_time_alarm_clock_in_automations_scripts_{self.entity_id}",
                breaks_in_ha_version="2025.10.0",
                is_fixable=True,
                is_persistent=True,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_time_alarm_clock",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "items": "\n".join(items_list),
                },
            )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        if self.bsh_key is SettingKey.BSH_COMMON_ALARM_CLOCK:
            async_delete_issue(
                self.hass,
                DOMAIN,
                f"deprecated_time_alarm_clock_in_automations_scripts_{self.entity_id}",
            )
            async_delete_issue(
                self.hass, DOMAIN, f"deprecated_time_alarm_clock_{self.entity_id}"
            )

    async def async_set_value(self, value: time) -> None:
        """Set the native value of the entity."""
        async_create_issue(
            self.hass,
            DOMAIN,
            f"deprecated_time_alarm_clock_{self.entity_id}",
            breaks_in_ha_version="2025.10.0",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_time_alarm_clock",
            translation_placeholders={
                "entity_id": self.entity_id,
            },
        )
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey(self.bsh_key),
                value=time_to_seconds(value),
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_setting_entity",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "entity_id": self.entity_id,
                    "key": self.bsh_key,
                    "value": str(value),
                },
            ) from err

    def update_native_value(self) -> None:
        """Set the value of the entity."""
        data = self.appliance.settings[cast(SettingKey, self.bsh_key)]
        self._attr_native_value = seconds_to_time(data.value)
