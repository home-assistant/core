"""Support for hunterdouglass_powerview switches."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final

from aiopvapi.helpers.constants import ATTR_NAME, FUNCTION_SCHEDULE
from aiopvapi.resources.automation import Automation

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import HDEntity
from .model import PowerviewDeviceInfo, PowerviewEntryData

_LOGGER = logging.getLogger(__name__)


@dataclass
class PowerviewSwitchDescriptionMixin:
    """Mixin to describe a Switch entity."""

    toggle_fn: Callable[[Automation, bool], Any]
    update_fn: Callable[[Automation], Any]
    value_fn: Callable[[Automation], bool]
    create_entity_fn: Callable[[Automation], bool]


@dataclass
class PowerviewSwitchDescription(
    SwitchEntityDescription, PowerviewSwitchDescriptionMixin
):
    """Class to describe a Switch entity."""

    entity_category = EntityCategory.CONFIG


SWITCHES: Final = [
    PowerviewSwitchDescription(
        key="schedule",
        name="Schedule",
        icon="mdi:calendar-clock",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda automation: automation.enabled,
        toggle_fn=lambda automation, state: automation.set_state(state),
        update_fn=lambda automation: automation.refresh(),
        create_entity_fn=lambda automation: automation.is_supported(FUNCTION_SCHEDULE),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas switch entities."""

    pv_entry: PowerviewEntryData = hass.data[DOMAIN][entry.entry_id]

    entities: list[PowerViewSwitch] = []
    for automation in pv_entry.automation_data.values():
        room_name = getattr(pv_entry.room_data.get(automation.room_id), ATTR_NAME, "")
        for description in SWITCHES:
            if description.create_entity_fn(automation):
                entities.append(
                    PowerViewSwitch(
                        pv_entry.coordinator,
                        pv_entry.device_info,
                        room_name,
                        automation,
                        description,
                    )
                )

    async_add_entities(entities)


class PowerViewSwitch(HDEntity, SwitchEntity):
    """Representation of an shade switch."""

    entity_description: PowerviewSwitchDescription

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        automation: Automation,
        description: PowerviewSwitchDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, device_info, room_name, automation.id)
        self.entity_description = description
        self._automation = automation
        self._attr_name = f"{automation.name} {description.name}"
        self._attr_unique_id = f"{automation.name}_{description.key}_{automation.id}"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return self._automation.details

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.entity_description.value_fn(self._automation)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.toggle_fn(self._automation, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.toggle_fn(self._automation, False)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Refresh switch entity."""
        await self.entity_description.update_fn(self._automation)
        self.async_write_ha_state()
