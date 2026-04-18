"""Demo platform that offers a fake radio frequency entity."""

from __future__ import annotations

from rf_protocols import RadioFrequencyCommand

from homeassistant.components import persistent_notification
from homeassistant.components.radio_frequency import RadioFrequencyTransmitterEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo radio frequency platform."""
    async_add_entities(
        [
            DemoRadioFrequency(
                unique_id="rf_transmitter",
                device_name="RF Blaster",
                entity_name="Radio Frequency Transmitter",
            ),
        ]
    )


class DemoRadioFrequency(RadioFrequencyTransmitterEntity):
    """Representation of a demo radio frequency entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        entity_name: str,
    ) -> None:
        """Initialize the demo radio frequency entity."""
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_name = entity_name

    @property
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return supported frequency ranges."""
        return [(300_000_000, 928_000_000)]

    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command."""
        persistent_notification.async_create(
            self.hass,
            str(command.get_raw_timings()),
            title="Radio Frequency Command",
        )
