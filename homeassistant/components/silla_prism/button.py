"""Silla Prism button entity module."""

from typing import override

from homeassistant.components import mqtt
from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import _get_unique_id
from .entry_data import RuntimeEntryData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    entry_data: RuntimeEntryData = entry.runtime_data

    ports = entry_data.ports
    selects = []
    for port in range(1, ports + 1):
        selects.extend(
            [PrismCommand(entry_data, description, port) for description in BUTTONS]
        )
    async_add_entities(selects)


class PrismCommandEntityDescription(ButtonEntityDescription, frozen_or_thawed=True):
    """A class that describes prism binary sensor entities."""

    command: str | None = None
    parameter: str | None = None


class PrismCommand(ButtonEntity):
    """A Command entity for Prism wallbox devices."""

    _attr_has_entity_name = True

    entity_description: PrismCommandEntityDescription

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        description: PrismCommandEntityDescription,
        port: int,
    ) -> None:
        """Init Prism select."""
        super().__init__()
        self._base_topic = entry_data.topic
        self._port = port
        self._attr_device_info = self._get_device(entry_data, port)
        self.entity_description = description
        self._attr_unique_id = _get_unique_id(entry_data.serial, description.key)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to mqtt."""
        await super().async_added_to_hass()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from mqtt."""
        await super().async_will_remove_from_hass()

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await mqtt.async_publish(
            self.hass,
            self._get_topic(),
            self.entity_description.parameter,
        )

    def _get_device(self, entry_data: RuntimeEntryData, port: int) -> DeviceInfo:
        """Get the device info."""
        ismultiport = entry_data.ports > 1
        if not ismultiport:
            return entry_data.devices[0]
        return entry_data.devices[port]

    def _get_topic(self) -> str:
        """Get the topic."""
        return (
            f"{self._base_topic}{self._port}/command/{self.entity_description.command}"
        )


BUTTONS: tuple[PrismCommandEntityDescription, ...] = (
    PrismCommandEntityDescription(
        key="set_mode_traps_auth",
        has_entity_name=True,
        translation_key="set_mode_traps_auth",
        command="set_mode_traps",
        device_class=ButtonDeviceClass.IDENTIFY,
        parameter="-auth",
    ),
    PrismCommandEntityDescription(
        key="set_mode_traps_noauth",
        has_entity_name=True,
        translation_key="set_mode_traps_noauth",
        command="set_mode_traps",
        device_class=ButtonDeviceClass.IDENTIFY,
        parameter="+auth",
    ),
)
