"""Switch entity for Electrolux Integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.hb_appliance import HBAppliance
from electrolux_group_developer_sdk.constants import (
    RC_ENABLED,
    RC_NOT_SAFETY_RELEVANT_ENABLED,
)
from electrolux_group_developer_sdk.feature_constants import CHILD_LOCK

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper


@dataclass(frozen=True, kw_only=True)
class ElectroluxSwitchDescription[T: ApplianceData](SwitchEntityDescription):
    """Custom switch description for Electrolux switches."""

    exists_fn: Callable[[T], bool]
    value_fn: Callable[[T], bool | None]
    turn_on_fn: Callable[[T], dict[str, Any]]
    turn_off_fn: Callable[[T], dict[str, Any]] | None = None
    remote_control_required: bool = False


HOB_ELECTROLUX_SWITCHES: tuple[ElectroluxSwitchDescription[HBAppliance], ...] = (
    ElectroluxSwitchDescription[HBAppliance](
        key="child_lock",
        translation_key="child_lock",
        exists_fn=lambda appliance: appliance.is_feature_supported(CHILD_LOCK),
        value_fn=lambda appliance: appliance.get_current_child_lock(),
        turn_on_fn=lambda appliance: appliance.get_enable_child_lock_command(),
        remote_control_required=True,
    ),
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, HBAppliance):
        entities.extend(
            ElectroluxSwitch(appliance_data, coordinator, description)
            for description in HOB_ELECTROLUX_SWITCHES
            if description.exists_fn(appliance_data)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set Switch entity for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxSwitch[T: HBAppliance](ElectroluxBaseEntity[T], SwitchEntity):
    """Representation of a generic switch for Electrolux appliances."""

    entity_description: ElectroluxSwitchDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSwitchDescription[T],
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            appliance_data,
            coordinator,
            description.key,
        )
        self.entity_description = description

    @override
    def _update_attr_state(self) -> bool:
        new_value = self.entity_description.value_fn(self._appliance_data)
        if self._attr_is_on != new_value:
            self._attr_is_on = new_value
            return True

        return False

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._check_remote_control_enabled()
        await self._async_send_command(self.entity_description.turn_on_fn)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        turn_off_fn = self.entity_description.turn_off_fn
        if turn_off_fn is None:
            raise ServiceValidationError(
                f"The {self.entity_description.name} cannot be turned off remotely"
            )
        self._check_remote_control_enabled()
        await self._async_send_command(turn_off_fn)

    async def _async_send_command(
        self, command_fn: Callable[..., dict[str, Any]]
    ) -> None:
        command = command_fn(self._appliance_data)
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    def _check_remote_control_enabled(self) -> None:
        if (
            self.entity_description.remote_control_required
            and self._appliance_data.get_current_remote_control()
            not in (RC_ENABLED, RC_NOT_SAFETY_RELEVANT_ENABLED)
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="remote_control_disabled"
            )
