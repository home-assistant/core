"""Switch platform for the BLUETTI Modbus integration."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BluettiModbusConfigEntry
from .entity import BluettiModbusSettingEntity

# The device takes one Modbus request at a time.
PARALLEL_UPDATES = 1

SWITCH_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="ac_o_switch",
        translation_key="ac_output",
        # Turning it off cuts whatever is plugged into the AC output, so it
        # has to be enabled on purpose.
        entity_registry_enabled_default=False,
    ),
    SwitchEntityDescription(
        key="g_i_switch",
        translation_key="grid_charging",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="g_o_switch",
        translation_key="grid_feed_in",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluettiModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLUETTI Modbus switches from a config entry."""
    async_add_entities(
        BluettiModbusSwitch(entry=entry, description=description)
        for description in SWITCH_DESCRIPTIONS
    )


class BluettiModbusSwitch(BluettiModbusSettingEntity, SwitchEntity):
    """Defines a BLUETTI Modbus switch."""

    def __init__(
        self, *, entry: BluettiModbusConfigEntry, description: SwitchEntityDescription
    ) -> None:
        """Initialize a BLUETTI Modbus switch."""
        super().__init__(entry=entry, field_name=description.key)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the switch is on."""
        return bool(self.coordinator.data[self._field_name])

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_write(1)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_write(0)
