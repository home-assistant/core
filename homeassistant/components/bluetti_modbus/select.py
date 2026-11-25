"""Select platform for the BLUETTI Modbus integration."""

from typing import override

from bluetti_modbus_lib import BalcoWorkingMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BluettiModbusConfigEntry
from .entity import BluettiModbusSettingEntity

# The device takes one Modbus request at a time.
PARALLEL_UPDATES = 1

WORKING_MODES: dict[str, BalcoWorkingMode] = {
    "custom": BalcoWorkingMode.Custom,
    "self_consumption": BalcoWorkingMode.SelfConsumption,
    "backup": BalcoWorkingMode.Backup,
}
WORKING_MODE_OPTIONS = {member: option for option, member in WORKING_MODES.items()}

WORKING_MODE_DESCRIPTION = SelectEntityDescription(
    key="d_working_mode",
    translation_key="working_mode",
    options=list(WORKING_MODES),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluettiModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLUETTI Modbus selects."""
    async_add_entities(
        [
            BluettiModbusWorkingModeSelect(
                entry=entry, description=WORKING_MODE_DESCRIPTION
            )
        ]
    )


class BluettiModbusWorkingModeSelect(BluettiModbusSettingEntity, SelectEntity):
    """Defines the BLUETTI Modbus working mode select."""

    def __init__(
        self, *, entry: BluettiModbusConfigEntry, description: SelectEntityDescription
    ) -> None:
        """Initialize the BLUETTI Modbus working mode select."""
        super().__init__(entry=entry, field_name=description.key)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Return whether the working mode can be read and written."""
        # The library stops reading the mode, and leaves it out of its values,
        # on a firmware that refuses the register.
        return super().available and self._field_name in self.coordinator.data

    @property
    @override
    def current_option(self) -> str | None:
        """Return the working mode."""
        # The library reads a mode it does not know as None.
        if (mode := self.coordinator.data[self._field_name]) is None:
            return None
        return WORKING_MODE_OPTIONS[mode]

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the working mode to the device."""
        await self._async_write(WORKING_MODES[option])
