"""GoodWe PV inverter selection settings entities."""
import logging

from goodwe import Inverter, InverterError, OperationMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_DEVICE_INFO, KEY_INVERTER

_LOGGER = logging.getLogger(__name__)


_MODE_TO_OPTION: dict[OperationMode, str] = {
    OperationMode.GENERAL: "general",
    OperationMode.OFF_GRID: "off_grid",
    OperationMode.BACKUP: "backup",
    OperationMode.ECO: "eco",
    OperationMode.PEAK_SHAVING: "peak_shaving",
    OperationMode.ECO_CHARGE: "eco_charge",
    OperationMode.ECO_DISCHARGE: "eco_discharge",
}

_OPTION_TO_MODE: dict[str, OperationMode] = {
    value: key for key, value in _MODE_TO_OPTION.items()
}

OPERATION_MODE = SelectEntityDescription(
    key="operation_mode",
    icon="mdi:solar-power",
    entity_category=EntityCategory.CONFIG,
    translation_key="operation_mode",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the inverter select entities from a config entry."""
    inverter = hass.data[DOMAIN][config_entry.entry_id][KEY_INVERTER]
    device_info = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE_INFO]

    supported_modes = await inverter.get_operation_modes(False)
    # read current operating mode from the inverter
    try:
        active_mode = await inverter.get_operation_mode()
    except (InverterError, ValueError):
        # Inverter model does not support this setting
        _LOGGER.debug("Could not read inverter operation mode")
    else:
        async_add_entities(
            [
                InverterOperationModeEntity(
                    device_info,
                    OPERATION_MODE,
                    inverter,
                    [v for k, v in _MODE_TO_OPTION.items() if k in supported_modes],
                    _MODE_TO_OPTION[active_mode],
                )
            ]
        )


class InverterOperationModeEntity(SelectEntity):
    """Entity representing the inverter operation mode."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device_info: DeviceInfo,
        description: SelectEntityDescription,
        inverter: Inverter,
        supported_options: list[str],
        current_mode: str,
    ) -> None:
        """Initialize the inverter operation mode setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_options = supported_options
        self._attr_current_option = current_mode
        self._inverter: Inverter = inverter

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._inverter.set_operation_mode(_OPTION_TO_MODE[option])
        self._attr_current_option = option
        self.async_write_ha_state()
