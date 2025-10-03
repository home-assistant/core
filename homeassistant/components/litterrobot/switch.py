"""Support for Litter-Robot switches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic

from pylitterbot import FeederRobot, LitterRobot, LitterRobot3, LitterRobot4, Robot

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN
from .coordinator import LitterRobotConfigEntry
from .entity import LitterRobotEntity, _WhiskerEntityT


@dataclass(frozen=True, kw_only=True)
class RobotSwitchEntityDescription(SwitchEntityDescription, Generic[_WhiskerEntityT]):
    """A class that describes robot switch entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG
    set_fn: Callable[[_WhiskerEntityT, bool], Coroutine[Any, Any, bool]]
    value_fn: Callable[[_WhiskerEntityT], bool]


NIGHT_LIGHT_MODE_ENTITY_DESCRIPTION = RobotSwitchEntityDescription[
    LitterRobot | FeederRobot
](
    key="night_light_mode_enabled",
    translation_key="night_light_mode",
    set_fn=lambda robot, value: robot.set_night_light(value),
    value_fn=lambda robot: robot.night_light_mode_enabled,
)

SWITCH_MAP: dict[type[Robot], tuple[RobotSwitchEntityDescription, ...]] = {
    FeederRobot: (
        RobotSwitchEntityDescription[FeederRobot](
            key="gravity_mode",
            translation_key="gravity_mode",
            set_fn=lambda robot, value: robot.set_gravity_mode(value),
            value_fn=lambda robot: robot.gravity_mode_enabled,
        ),
        NIGHT_LIGHT_MODE_ENTITY_DESCRIPTION,
    ),
    LitterRobot3: (NIGHT_LIGHT_MODE_ENTITY_DESCRIPTION,),
    Robot: (  # type: ignore[type-abstract]  # only used for isinstance check
        RobotSwitchEntityDescription[LitterRobot | FeederRobot](
            key="panel_lock_enabled",
            translation_key="panel_lockout",
            set_fn=lambda robot, value: robot.set_panel_lockout(value),
            value_fn=lambda robot: robot.panel_lock_enabled,
        ),
    ),
    LitterRobot: (
        RobotSwitchEntityDescription[LitterRobot](
            key="power",
            translation_key="power",
            set_fn=lambda robot, value: robot.set_power_status(value),
            value_fn=lambda robot: robot.power_status == "AC",
            entity_registry_enabled_default=False,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot switches using config entry."""
    coordinator = entry.runtime_data
    entities = [
        RobotSwitchEntity(robot=robot, coordinator=coordinator, description=description)
        for robot in coordinator.account.robots
        for robot_type, entity_descriptions in SWITCH_MAP.items()
        if isinstance(robot, robot_type)
        for description in entity_descriptions
    ]

    ent_reg = er.async_get(hass)

    def add_deprecated_entity(
        robot: LitterRobot4,
        description: RobotSwitchEntityDescription,
        entity_cls: type[RobotSwitchEntity],
    ) -> None:
        """Add deprecated entities."""
        unique_id = f"{robot.serial}-{description.key}"
        if entity_id := ent_reg.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, unique_id):
            entity_entry = ent_reg.async_get(entity_id)
            if entity_entry and entity_entry.disabled:
                ent_reg.async_remove(entity_id)
                async_delete_issue(
                    hass,
                    DOMAIN,
                    f"deprecated_entity_{unique_id}",
                )
            elif entity_entry:
                entities.append(entity_cls(robot, coordinator, description))
                async_create_issue(
                    hass,
                    DOMAIN,
                    f"deprecated_entity_{unique_id}",
                    breaks_in_ha_version="2026.4.0",
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_entity",
                    translation_placeholders={
                        "name": f"{robot.name} {entity_entry.name or entity_entry.original_name}",
                        "entity": entity_id,
                    },
                )

    for robot in coordinator.account.get_robots(LitterRobot4):
        add_deprecated_entity(
            robot, NIGHT_LIGHT_MODE_ENTITY_DESCRIPTION, RobotSwitchEntity
        )

    async_add_entities(entities)


class RobotSwitchEntity(LitterRobotEntity[_WhiskerEntityT], SwitchEntity):
    """Litter-Robot switch entity."""

    entity_description: RobotSwitchEntityDescription[_WhiskerEntityT]

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.value_fn(self.robot)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_fn(self.robot, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.robot, False)
