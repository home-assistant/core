"""Select entities for Beatbot."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeatbotConfigEntry
from .coordinator import BeatbotCoordinator
from .entity import BeatbotEntity

_LOGGER = logging.getLogger(__name__)


class BeatbotWorkModeSelect(BeatbotEntity, SelectEntity):
    """Work mode selector backed by the device's select.work_mode capability."""

    _attr_translation_key = "work_mode"

    def __init__(self, coordinator: BeatbotCoordinator, device_id: str) -> None:
        """Initialize the work-mode select."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_work_mode"
        self._attr_options = list(self.data.work_mode_options.values())
        self._option_to_value = {
            label: value for value, label in self.data.work_mode_options.items()
        }

    @property
    def available(self) -> bool:
        """Return whether the work mode can be controlled."""
        return self.data.is_online and self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        """Return the active work-mode label."""
        return self.data.work_mode_options.get(self.data.work_mode)

    async def async_select_option(self, option: str) -> None:
        """Set the device work mode."""
        if option not in self._option_to_value:
            _LOGGER.warning(
                "Unknown work mode %r for %s; ignoring", option, self._device_id
            )
            return
        target_value = self._option_to_value[option]
        await self._async_send_command(
            self.coordinator.api.set_work_mode(self._device_id, option)
        )
        # The command response confirms acceptance, but the cloud state event
        # arrives later. Apply the selected value immediately so HA does not
        # render the old coordinator value after the service call completes
        # and then jump forward again when WebSocket reconciliation arrives.
        self.coordinator.async_apply_device_event(
            self._device_id, {"select.work_mode": target_value}
        )
        _LOGGER.info(
            "Applied Beatbot work mode after successful command "
            "(deviceId=%s, option=%s, value=%s)",
            self._device_id,
            option,
            target_value,
        )
        self.coordinator.async_schedule_device_state_refresh(self._device_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeatbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Beatbot work-mode selects."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        BeatbotWorkModeSelect(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device.work_mode_options
    )
