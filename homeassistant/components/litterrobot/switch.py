"""Support for Litter-Robot switches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Generic

from pylitterbot import FeederRobot, LitterRobot, LitterRobot4

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
    types: list[_WhiskerEntityT]
    type_breaks_in_ha_version: dict[_WhiskerEntityT, str] = field(default_factory=dict)


SWITCH_LIST: list[RobotSwitchEntityDescription] = [
    RobotSwitchEntityDescription[LitterRobot](
        key="power",
        translation_key="power",
        entity_registry_enabled_default=False,
        set_fn=lambda robot, value: robot.set_power_status(value),
        value_fn=lambda robot: robot.power_status != "NC",
        types=[
            LitterRobot,
        ],
    ),
    RobotSwitchEntityDescription[FeederRobot](
        key="gravity_mode",
        translation_key="gravity_mode",
        set_fn=lambda robot, value: robot.set_gravity_mode(value),
        value_fn=lambda robot: robot.gravity_mode_enabled,
        types=[
            FeederRobot,
        ],
    ),
    RobotSwitchEntityDescription[LitterRobot | FeederRobot](
        key="panel_lock_enabled",
        translation_key="panel_lockout",
        set_fn=lambda robot, value: robot.set_panel_lockout(value),
        value_fn=lambda robot: robot.panel_lock_enabled,
        types=[
            LitterRobot,
            FeederRobot,
        ],
    ),
    RobotSwitchEntityDescription[LitterRobot | FeederRobot](
        key="night_light_mode_enabled",
        translation_key="night_light_mode",
        set_fn=lambda robot, value: robot.set_night_light(value),
        value_fn=lambda robot: robot.night_light_mode_enabled,
        types=[
            LitterRobot,
            FeederRobot,
        ],
        type_breaks_in_ha_version={
            LitterRobot4: "2026.4.0",
        },
    ),
]


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
        for description in SWITCH_LIST
        if any(isinstance(robot, robot_type) for robot_type in description.types)
    ]
    deprecated_entities = [
        (robot, description, breaks_in_ha_version)
        for robot in coordinator.account.robots
        for description in SWITCH_LIST
        if description.type_breaks_in_ha_version
        for deprecated_type, breaks_in_ha_version in description.type_breaks_in_ha_version.items()
        if isinstance(robot, deprecated_type)
    ]

    ent_reg = er.async_get(hass)

    def add_deprecated_entity(
        robot: type[_WhiskerEntityT],
        description: RobotSwitchEntityDescription,
        entity_cls: type[RobotSwitchEntity],
        breaks_in_ha_version: str,
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
                    breaks_in_ha_version=breaks_in_ha_version,
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_entity",
                    translation_placeholders={
                        "name": f"{robot.name} {entity_entry.name or entity_entry.original_name}",
                        "entity": entity_id,
                    },
                )

    for robot, description, breaks_in_ha_version in deprecated_entities:
        add_deprecated_entity(
            robot, description, RobotSwitchEntity, breaks_in_ha_version
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
