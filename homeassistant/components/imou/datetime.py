"""Support for Imou datetime entities."""

from datetime import datetime
from typing import override

from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.datetime import DateTimeEntity, DateTimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PARAM_COUNT_DOWN_SWITCH, imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .countdown import minutes_until
from .entity import ImouEntity
from .helpers import async_wrap_imou_command

PARALLEL_UPDATES = 0

COUNTDOWN_DATETIME = DateTimeEntityDescription(
    key=PARAM_COUNT_DOWN_SWITCH,
    translation_key=PARAM_COUNT_DOWN_SWITCH,
    entity_category=EntityCategory.CONFIG,
)


def _iter_countdown_datetimes(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[DateTimeEntityDescription, ImouHaDevice]]:
    """Return countdown datetimes for plugs that expose the timer."""
    return [
        (COUNTDOWN_DATETIME, device)
        for device in coordinator.devices
        if PARAM_COUNT_DOWN_SWITCH in device.texts
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou datetime entities."""
    coordinator = entry.runtime_data

    def _add_datetimes(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouCountdownDateTime(coordinator, description, device)
            for description, device in _iter_countdown_datetimes(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    entry.async_on_unload(coordinator.register_new_device_callback(_add_datetimes))
    _add_datetimes(coordinator.devices)


class ImouCountdownDateTime(ImouEntity, DateTimeEntity):
    """When a supported smart plug will turn off.

    The cloud API stores remaining minutes. This entity exposes the end time so
    Home Assistant does not rewrite state every minute while the timer runs.
    """

    entity_description: DateTimeEntityDescription

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return when the countdown ends, or None when idle."""
        return self.coordinator.countdown.ends_at(self._device_key)

    @override
    async def async_set_value(self, value: datetime) -> None:
        """Write remaining minutes derived from the chosen end time."""
        minutes = minutes_until(value)
        await self._async_write_text(str(minutes))
        self.coordinator.countdown.start_minutes(
            self.hass, self.coordinator, self._device_key, minutes
        )
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Continue a countdown that the last status refresh already reported."""
        await super().async_added_to_hass()
        self.coordinator.countdown.seed_if_idle(
            self.hass, self.coordinator, self.device
        )
        self.async_write_ha_state()

    @async_wrap_imou_command("set_text_value_failed")
    async def _async_write_text(self, text_value: str) -> None:
        await self.coordinator.device_manager.async_set_text_value(
            self.device,
            PARAM_COUNT_DOWN_SWITCH,
            text_value,
        )
