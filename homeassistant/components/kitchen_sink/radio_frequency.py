"""Demo platform that offers a fake radio frequency entity."""

from dataclasses import dataclass
from typing import override

from rf_protocols import RadioFrequencyCommand

from homeassistant.components import persistent_notification
from homeassistant.components.radio_frequency import (
    RadioFrequencyTransmitterEntity,
    RadioFrequencyTransmitterEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DemoRadioFrequencyEntityDescription(RadioFrequencyTransmitterEntityDescription):
    """Describes a demo radio frequency entity."""

    device_name: str


TRANSMITTERS = (
    DemoRadioFrequencyEntityDescription(
        key="rf_transmitter",
        name="Radio Frequency Transmitter",
        device_name="RF Blaster",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo radio frequency platform."""
    async_add_entities(DemoRadioFrequency(description) for description in TRANSMITTERS)


class DemoRadioFrequency(RadioFrequencyTransmitterEntity):
    """Representation of a demo radio frequency entity."""

    entity_description: DemoRadioFrequencyEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, description: DemoRadioFrequencyEntityDescription) -> None:
        """Initialize the demo radio frequency entity."""
        self.entity_description = description
        self._attr_unique_id = description.key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, description.key)},
            name=description.device_name,
        )

    @property
    @override
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return supported frequency ranges."""
        return [(300_000_000, 928_000_000)]

    @override
    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command."""
        persistent_notification.async_create(
            self.hass,
            str(command.get_raw_timings()),
            title="Radio Frequency Command",
        )
