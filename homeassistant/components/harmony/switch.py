"""Support for Harmony Hub activities."""

import logging
from typing import Any, cast

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, HARMONY_DATA
from .data import HarmonyData
from .entity import HarmonyEntity
from .subscriber import HarmonyCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up harmony activity switches."""
    data: HarmonyData = hass.data[DOMAIN][entry.entry_id][HARMONY_DATA]

    async_add_entities(
        (HarmonyActivitySwitch(activity, data) for activity in data.activities), True
    )


class HarmonyActivitySwitch(HarmonyEntity, SwitchEntity):
    """Switch representation of a Harmony activity."""

    def __init__(self, activity: dict, data: HarmonyData) -> None:
        """Initialize HarmonyActivitySwitch class."""
        super().__init__(data=data)
        self._activity_name = self._attr_name = activity["label"]
        self._activity_id = activity["id"]
        self._attr_entity_registry_enabled_default = False
        self._attr_unique_id = f"activity_{self._activity_id}"
        self._attr_device_info = self._data.device_info(DOMAIN)

    @property
    def is_on(self) -> bool:
        """Return if the current activity is the one for this switch."""
        _, activity_name = self._data.current_activity
        return activity_name == self._activity_name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start this activity."""
        async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_switches",
            breaks_in_ha_version="2024.6.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_switches",
        )
        await self._data.async_start_activity(self._activity_name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop this activity."""
        async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_switches",
            breaks_in_ha_version="2024.6.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_switches",
        )
        await self._data.async_power_off()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        activity_update_job = HassJob(self._async_activity_update)
        self.async_on_remove(
            self._data.async_subscribe(
                HarmonyCallback(
                    connected=HassJob(self.async_got_connected),
                    disconnected=HassJob(self.async_got_disconnected),
                    activity_starting=activity_update_job,
                    activity_started=activity_update_job,
                    config_updated=None,
                )
            )
        )
        entity_automations = automations_with_entity(self.hass, self.entity_id)
        entity_scripts = scripts_with_entity(self.hass, self.entity_id)
        for item in entity_automations + entity_scripts:
            async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_switches_{self.entity_id}_{item}",
                breaks_in_ha_version="2024.6.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_switches_entity",
                translation_placeholders={
                    "entity": f"{SWITCH_DOMAIN}.{cast(str, self.name).lower().replace(' ', '_')}",
                    "info": item,
                },
            )

    @callback
    def _async_activity_update(self, activity_info: tuple) -> None:
        self.async_write_ha_state()
