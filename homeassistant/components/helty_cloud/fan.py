"""Fan platform for the Helty Flow Cloud integration."""

from typing import Any, override

from pyheltycloud import HeltyCloudError, VmcMode

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN, PRESET_BOOST, PRESET_FREE_COOLING, PRESET_NIGHT
from .coordinator import HeltyCloudConfigEntry, HeltyCloudDataUpdateCoordinator
from .entity import HeltyCloudEntity

PARALLEL_UPDATES = 1

# How many times a mode command is sent before the change is called failed.
# Each attempt wakes the panel, which the manufacturer asks to keep rare, so
# this only buys one retry for the command the cloud happened to drop.
SET_MODE_ATTEMPTS = 2

# Ordered list of discrete fan speeds, lowest to highest.
ORDERED_SPEEDS: list[VmcMode] = [
    VmcMode.SPEED_1,
    VmcMode.SPEED_2,
    VmcMode.SPEED_3,
    VmcMode.SPEED_4,
]

PRESET_TO_MODE: dict[str, VmcMode] = {
    PRESET_BOOST: VmcMode.HYPERVENTILATION,
    PRESET_NIGHT: VmcMode.NIGHT,
    PRESET_FREE_COOLING: VmcMode.FREE_COOLING,
}
MODE_TO_PRESET: dict[VmcMode, str] = {
    mode: preset for preset, mode in PRESET_TO_MODE.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeltyCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fan of every VMC on the account."""
    async_add_entities(HeltyCloudFan(coordinator) for coordinator in entry.runtime_data)


class HeltyCloudFan(HeltyCloudEntity, FanEntity):
    """The ventilation unit's fan, the device's primary feature."""

    _attr_name = None
    _attr_translation_key = "ventilation"
    _attr_speed_count = len(ORDERED_SPEEDS)
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: HeltyCloudDataUpdateCoordinator) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device.serial_number
        self._attr_preset_modes = list(PRESET_TO_MODE)

    @property
    def _mode(self) -> VmcMode:
        return self.coordinator.data.mode

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the fan is running."""
        return self._mode is not VmcMode.OFF

    @property
    @override
    def percentage(self) -> int | None:
        """Return the current speed as a percentage, or None when on a preset."""
        if self._mode in ORDERED_SPEEDS:
            return ordered_list_item_to_percentage(ORDERED_SPEEDS, self._mode)
        return None

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the active preset, or None when running on a discrete speed."""
        return MODE_TO_PRESET.get(self._mode)

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set a discrete fan speed from a percentage."""
        if percentage == 0:
            await self._async_set_mode(VmcMode.OFF)
            return
        await self._async_set_mode(
            percentage_to_ordered_list_item(ORDERED_SPEEDS, percentage)
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a preset mode."""
        await self._async_set_mode(PRESET_TO_MODE[preset_mode])

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._async_set_mode(VmcMode.SPEED_1)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._async_set_mode(VmcMode.OFF)

    async def _async_set_mode(self, mode: VmcMode) -> None:
        """Set the mode and confirm the panel applied it.

        The cloud takes a command and answers before the panel has acted on
        it, and only ever serves the last message the panel sent, so the new
        mode is not visible until the panel reports again: the read back
        prompts it, and takes about three seconds. A command can be lost on
        the way, and reading alone cannot tell that apart from a panel that
        has not reported yet, so the mode is compared and sent once more
        before giving up.
        """
        device = self.coordinator.device
        try:
            state = await self.coordinator.client.set_mode_verified(
                device, mode, attempts=SET_MODE_ATTEMPTS
            )
        except HeltyCloudError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_fan_mode_failed",
            ) from err
        self.coordinator.async_set_updated_data(state)
