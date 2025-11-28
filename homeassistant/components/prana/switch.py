"""Switch platform for Prana integration."""

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PranaConfigEntry
from .const import DOMAIN, PranaSwitchType
from .coordinator import PranaCoordinator

PARALLEL_UPDATES = 1

# Add entity descriptions for each switch type
SWITCH_DESCRIPTIONS: dict[str, SwitchEntityDescription] = {
    PranaSwitchType.BOUND: SwitchEntityDescription(
        key="bounded", translation_key="bound"
    ),
    PranaSwitchType.HEATER: SwitchEntityDescription(
        key="heater", translation_key="heater"
    ),
    PranaSwitchType.AUTO: SwitchEntityDescription(key="auto", translation_key="auto"),
    PranaSwitchType.AUTO_PLUS: SwitchEntityDescription(
        key="auto_plus", translation_key="auto_plus"
    ),
    PranaSwitchType.WINTER: SwitchEntityDescription(
        key="winter", translation_key="winter"
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PranaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana switch entities from a config entry."""
    async_add_entities(
        [
            PranaSwitch(
                unique_id=f"{entry.entry_id}-bound",
                switch_type=PranaSwitchType.BOUND,
                entry=entry,
            ),
            PranaSwitch(
                unique_id=f"{entry.entry_id}-heater",
                switch_type=PranaSwitchType.HEATER,
                entry=entry,
            ),
            PranaSwitch(
                unique_id=f"{entry.entry_id}-auto",
                switch_type=PranaSwitchType.AUTO,
                entry=entry,
            ),
            PranaSwitch(
                unique_id=f"{entry.entry_id}-auto_plus",
                switch_type=PranaSwitchType.AUTO_PLUS,
                entry=entry,
            ),
            PranaSwitch(
                unique_id=f"{entry.entry_id}-winter",
                switch_type=PranaSwitchType.WINTER,
                entry=entry,
            ),
        ]
    )


class PranaSwitch(CoordinatorEntity[PranaCoordinator], SwitchEntity):
    """Representation of a Prana switch (bound/heater/auto/etc)."""

    _attr_has_entity_name = True
    _attr_unique_id: str

    def __init__(
        self,
        unique_id: str,
        switch_type: str,
        entry: PranaConfigEntry,
    ) -> None:
        """Initialize switch entity."""
        super().__init__(coordinator=entry.runtime_data)
        self._attr_unique_id = unique_id
        self.entry = entry
        self.coordinator = entry.runtime_data
        self.switch_type = switch_type

        self.entity_description = SWITCH_DESCRIPTIONS.get(
            self.switch_type,
            SwitchEntityDescription(key="switch", translation_key="switch"),
        )
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name", "Prana Device"),
            manufacturer="Prana",
            model="PRANA RECUPERATOR",
        )

    @property
    def is_on(self) -> bool:
        """Return switch on/off state."""
        value = getattr(self.coordinator.data, self.switch_type, False)
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entry.runtime_data.api_client.set_switch(self.switch_type, True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entry.runtime_data.api_client.set_switch(self.switch_type, False)
        await self.coordinator.async_refresh()
