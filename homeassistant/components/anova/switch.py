"""Support for Anova Switches."""

from typing import Any, override

from anova_wifi import Capability, CommandFailure, WebsocketFailure

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import AnovaConfigEntry, AnovaCoordinator
from .entity import AnovaEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Anova switch entities."""
    anova_data = entry.runtime_data

    # anova-wifi 2.0.0 reports a3 temperatures in the device's display unit
    # and never publishes a cook time, so a cook started from those values
    # would be wrong; only expose a3 devices once Lash-L/anova_wifi#84 ships.
    async_add_entities(
        AnovaCookSwitch(coordinator)
        for coordinator in anova_data.coordinators
        if coordinator.anova_device.type != "a3"
        and {Capability.START_COOK, Capability.STOP_COOK}
        <= coordinator.anova_device.supported_capabilities
    )


class AnovaCookSwitch(AnovaEntity, SwitchEntity):
    """Starts or stops a cook.

    Turning on starts a cook using the target temperature and timer the
    coordinator currently holds - seeded from the device's own state, and
    adjustable via the Anova number entities. The switch stays available
    while a cook is running even if the pending values have not been seeded
    yet, so a running cook can always be stopped.
    """

    def __init__(self, coordinator: AnovaCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = SwitchEntityDescription(
            key="cook", translation_key="cook"
        )
        self._attr_unique_id = f"{coordinator.device_unique_id}_cook"

    @property
    @override
    def is_on(self) -> bool:
        """Return true if a cook is currently running."""
        return self.coordinator.anova_device.is_cooking

    @property
    @override
    def available(self) -> bool:
        """Return if the cook switch is available."""
        return super().available and (
            self.coordinator.anova_device.is_cooking
            or (
                self.coordinator.pending_target_temperature is not None
                and self.coordinator.pending_cook_time_seconds is not None
            )
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start a cook."""
        target_temperature = self.coordinator.pending_target_temperature
        cook_time_seconds = self.coordinator.pending_cook_time_seconds
        if target_temperature is None or cook_time_seconds is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="start_cook_unavailable",
            )
        try:
            await self.coordinator.anova_device.start_cook(
                target_temperature,
                cook_time_seconds,
                "C",
            )
        except (CommandFailure, WebsocketFailure) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="start_cook_failed",
            ) from ex

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the current cook."""
        try:
            await self.coordinator.anova_device.stop_cook()
        except (CommandFailure, WebsocketFailure) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stop_cook_failed",
            ) from ex
