"""Switch platform for Prana integration."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PranaSwitchType
from .coordinator import PranaCoordinator

PARALLEL_UPDATES = 1


class PranaSendSwitch:
    """Helper to send switch state changes to device."""

    def __init__(
        self, value: bool, switch_type: str, coordinator: PranaCoordinator
    ) -> None:
        """Initialize switch sender."""
        self.value = value
        self.switch_type = switch_type
        self.coordinator = coordinator

    async def send(self) -> None:
        """Send the switch command."""

        try:
            await self.coordinator.api_client.set_switch(
                switch_type=self.switch_type, value=self.value
            )
        except Exception as err:
            raise HomeAssistantError(f"Error setting switch: {err}") from err


class PranaSwitch(SwitchEntity):
    """Representation of a Prana switch (bound/heater/auto/etc)."""

    _attr_has_entity_name = True
    _attr_unique_id: str
    _attr_translation_key: str | None = None

    def __init__(
        self,
        unique_id: str,
        coordinator: PranaCoordinator,
        switch_key: str,
        switch_type: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize switch entity."""
        self._attr_unique_id = unique_id
        self.coordinator = coordinator
        self.switch_key = switch_key
        self.switch_type = switch_type
        if self.switch_type == PranaSwitchType.BOUND:
            self._attr_translation_key = "bound"
        elif self.switch_type == PranaSwitchType.HEATER:
            self._attr_translation_key = "heater"
        elif self.switch_type == PranaSwitchType.AUTO:
            self._attr_translation_key = "auto"
        elif self.switch_type == PranaSwitchType.AUTO_PLUS:
            self._attr_translation_key = "auto_plus"
        elif self.switch_type == PranaSwitchType.WINTER:
            self._attr_translation_key = "winter"
        else:
            self._attr_translation_key = "switch"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name", "Prana Device"),
            manufacturer="Prana",
            model="PRANA RECUPERATOR",
        )
        self._attr_icon = self.get_icon()

    def get_icon(self) -> str:
        """Return icon for switch type."""
        if self.switch_type == PranaSwitchType.BOUND:
            return "mdi:link"
        if self.switch_type == PranaSwitchType.HEATER:
            return "mdi:radiator"
        if self.switch_type in (PranaSwitchType.AUTO, PranaSwitchType.AUTO_PLUS):
            return "mdi:fan-auto"
        if self.switch_type == PranaSwitchType.WINTER:
            return "mdi:snowflake"
        return "mdi:help"

    @property
    def is_on(self) -> bool:
        """Return switch on/off state."""
        value = self.coordinator.data.get(self.switch_key)
        if isinstance(value, dict):
            return bool(value.get("is_on", False))
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        sender = PranaSendSwitch(True, self.switch_type, self.coordinator)
        await sender.send()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        sender = PranaSendSwitch(False, self.switch_type, self.coordinator)
        await sender.send()
        await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """Register coordinator listener when entity added."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana switch entities from a config entry."""
    coordinator: PranaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PranaSwitch(
                unique_id=f"{entry.entry_id}-bound",
                coordinator=coordinator,
                switch_key="bounded",
                switch_type=PranaSwitchType.BOUND,
                entry=entry,
            ),
            PranaSwitch(
                unique_id=f"{entry.entry_id}-heater",
                coordinator=coordinator,
                switch_key="heater",
                switch_type=PranaSwitchType.HEATER,
                entry=entry,
            ),
            PranaSwitch(
                unique_id=f"{entry.entry_id}-auto",
                coordinator=coordinator,
                switch_key="Auto",
                switch_type=PranaSwitchType.AUTO,
                entry=entry,
            ),
            PranaSwitch(
                unique_id=f"{entry.entry_id}-auto_plus",
                coordinator=coordinator,
                switch_key="Auto Plus",
                switch_type=PranaSwitchType.AUTO_PLUS,
                entry=entry,
            ),
            PranaSwitch(
                unique_id=f"{entry.entry_id}-winter",
                coordinator=coordinator,
                switch_key="winter",
                switch_type=PranaSwitchType.WINTER,
                entry=entry,
            ),
        ]
    )
