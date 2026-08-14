"""Fan entity for Electrolux Integration."""

from typing import TYPE_CHECKING, Any, override

from electrolux_group_developer_sdk.client.appliances.ap_appliance import APAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .util import convert_to_snake_case


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, APAppliance):
        entities.append(
            AirPurifierFanEntity(
                appliance_data=appliance_data,
                coordinator=coordinator,
            )
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set Fan entity for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class AirPurifierFanEntity(ElectroluxBaseEntity[APAppliance], FanEntity):
    """Representation of an Electrolux Air purifier unit."""

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    def __init__(
        self,
        appliance_data: APAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize the fan device."""
        super().__init__(appliance_data, coordinator, "fan")
        self._attr_key = "fan"
        self._attr_translation_key = "air_purifier_fan"
        self._attr_preset_modes = self._get_supported_mode()
        self._modes_mapping = self._get_modes_mapping()
        self._speed_range = self._get_speed_range()
        self._attr_speed_count = int_states_in_range(self._speed_range)
        self._attr_preset_mode = None

    def _state_snapshot(self) -> dict[str, Any]:
        """Return a snapshot of the current state."""
        return {
            "is_on": self._attr_is_on,
            "percentage": self._attr_percentage,
            "preset_mode": self._attr_preset_mode,
        }

    @override
    def _update_attr_state(self) -> bool:
        old_state_snapeshot = self._state_snapshot()

        self._attr_is_on = self._is_ap_on()
        self._attr_percentage = self._get_current_fan_speed_percentage()
        self._attr_preset_mode = self._get_current_mode()

        new_state_snapshot = self._state_snapshot()

        return old_state_snapeshot != new_state_snapshot

    def _is_ap_on(self) -> bool:
        """Return true if the appliance is on."""
        return self._appliance_data.is_appliance_on()

    def _get_current_fan_speed_percentage(self) -> int:
        """Return current fan speed if the appliance is on."""
        if self._is_ap_on():
            return ranged_value_to_percentage(
                self._speed_range, self._get_current_speed()
            )
        return 0

    def _get_current_speed(self) -> int:
        """Return current fan speed."""
        return self._appliance_data.get_current_fan_speed() or 0

    def _get_current_mode(self) -> str | None:
        """Return current mode, if the appliance is on."""
        if self._is_ap_on():
            return convert_to_snake_case(self._appliance_data.get_current_mode())
        return None

    def _get_supported_mode(self) -> list[str]:
        """Return the supported modes."""
        return [key for (key, _) in self._get_modes_mapping().items()]

    def _get_modes_mapping(self) -> dict[str, str]:
        """Return a mapping from the Home Assistant representation to the appliance representation."""
        modes = self._appliance_data.get_supported_modes() or []

        return {
            convert_to_snake_case(mode): mode
            for mode in modes
            if mode != self._appliance_data.get_off_mode()
        }

    def _get_speed_range(self) -> tuple[int, int]:
        """Return the supported fan speed ranges."""
        min_range = self._appliance_data.get_supported_min_fan_speed()
        max_range = self._appliance_data.get_supported_max_fan_speed()

        if not min_range or not max_range:
            return (0, 0)

        if min_range == 0:
            min_range = 1
        return (
            min_range,
            max_range,
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Send set mode command."""
        mode = self._modes_mapping.get(preset_mode)
        if TYPE_CHECKING:
            # if preset_mode is one of the reported modes, then it is also present in _modes_mapping
            assert mode is not None
        command = self._appliance_data.get_mode_command(mode)
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Send set fan speed command. If fan speed percentage is 0 turn off the appliance."""
        fan_speed = round(
            percentage_to_ranged_value(
                percentage=percentage, low_high_range=self._speed_range
            )
        )
        if fan_speed == 0:
            await self.async_turn_off()
        else:
            command = self._appliance_data.get_fan_speed_command(fan_speed)
            await self.coordinator.client.send_command(self._appliance_id, command)
            await self.coordinator.async_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send turn off command."""
        command = self._appliance_data.get_turn_off_command()
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send turn on command."""
        command = self._appliance_data.get_turn_on_command()
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()
