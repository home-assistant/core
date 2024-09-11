"""Support for select entities."""

from __future__ import annotations

import logging

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode, ThinQPropertyEx

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity

SELECT_DESC: dict[ThinQProperty, SelectEntityDescription] = {
    ThinQProperty.MONITORING_ENABLED: SelectEntityDescription(
        key=ThinQProperty.MONITORING_ENABLED,
        translation_key=ThinQProperty.MONITORING_ENABLED,
    ),
    ThinQProperty.COOK_MODE: SelectEntityDescription(
        key=ThinQProperty.COOK_MODE,
        translation_key=ThinQProperty.COOK_MODE,
    ),
    ThinQProperty.POWER_SAVE_ENABLED: SelectEntityDescription(
        key=ThinQProperty.POWER_SAVE_ENABLED,
        translation_key=ThinQProperty.POWER_SAVE_ENABLED,
    ),
    ThinQProperty.DISPLAY_LIGHT: SelectEntityDescription(
        key=ThinQProperty.DISPLAY_LIGHT,
        translation_key=ThinQProperty.DISPLAY_LIGHT,
    ),
    ThinQPropertyEx.HUMIDITY_WARM_MODE: SelectEntityDescription(
        key=ThinQProperty.WARM_MODE,
        translation_key=ThinQPropertyEx.HUMIDITY_WARM_MODE,
    ),
    ThinQProperty.CURRENT_JOB_MODE: SelectEntityDescription(
        key=ThinQProperty.CURRENT_JOB_MODE,
        translation_key=ThinQProperty.CURRENT_JOB_MODE,
    ),
    ThinQProperty.UV_NANO: SelectEntityDescription(
        key=ThinQProperty.UV_NANO,
        translation_key=ThinQProperty.UV_NANO,
    ),
    ThinQProperty.MOOD_LAMP_STATE: SelectEntityDescription(
        key=ThinQProperty.MOOD_LAMP_STATE,
        translation_key=ThinQProperty.MOOD_LAMP_STATE,
    ),
}
AIR_FLOW_SELECT_DESC: dict[ThinQProperty, SelectEntityDescription] = {
    ThinQProperty.WIND_STRENGTH: SelectEntityDescription(
        key=ThinQProperty.WIND_STRENGTH,
        translation_key=ThinQProperty.WIND_STRENGTH,
    ),
    ThinQProperty.WIND_ANGLE: SelectEntityDescription(
        key=ThinQProperty.WIND_ANGLE,
        translation_key=ThinQProperty.WIND_ANGLE,
    ),
    ThinQProperty.WARM_MODE: SelectEntityDescription(
        key=ThinQProperty.WARM_MODE,
        translation_key=ThinQProperty.WARM_MODE,
    ),
}
OPERATION_SELECT_DESC: dict[ThinQProperty, SelectEntityDescription] = {
    ThinQProperty.AIR_CLEAN_OPERATION_MODE: SelectEntityDescription(
        key=ThinQProperty.AIR_CLEAN_OPERATION_MODE,
        translation_key="air_clean_operation_mode",
    ),
    ThinQProperty.AUTO_MODE: SelectEntityDescription(
        key=ThinQProperty.AUTO_MODE,
        translation_key=ThinQProperty.AUTO_MODE,
    ),
    ThinQProperty.DISH_WASHER_OPERATION_MODE: SelectEntityDescription(
        key=ThinQProperty.DISH_WASHER_OPERATION_MODE,
        translation_key="operation_mode",
    ),
    ThinQProperty.DRYER_OPERATION_MODE: SelectEntityDescription(
        key=ThinQProperty.DRYER_OPERATION_MODE,
        translation_key="operation_mode",
    ),
    ThinQProperty.HOT_WATER_MODE: SelectEntityDescription(
        key=ThinQProperty.HOT_WATER_MODE,
        translation_key=ThinQProperty.HOT_WATER_MODE,
    ),
    ThinQProperty.HYGIENE_DRY_MODE: SelectEntityDescription(
        key=ThinQProperty.HYGIENE_DRY_MODE,
        translation_key=ThinQProperty.HYGIENE_DRY_MODE,
    ),
    ThinQProperty.LIGHT_BRIGHTNESS: SelectEntityDescription(
        key=ThinQProperty.LIGHT_BRIGHTNESS,
        translation_key=ThinQProperty.LIGHT_BRIGHTNESS,
    ),
    ThinQProperty.OPTIMAL_HUMIDITY: SelectEntityDescription(
        key=ThinQProperty.OPTIMAL_HUMIDITY,
        translation_key=ThinQProperty.OPTIMAL_HUMIDITY,
    ),
    ThinQProperty.OVEN_OPERATION_MODE: SelectEntityDescription(
        key=ThinQProperty.OVEN_OPERATION_MODE,
        translation_key="operation_mode",
    ),
    ThinQProperty.SLEEP_MODE: SelectEntityDescription(
        key=ThinQProperty.SLEEP_MODE,
        translation_key=ThinQProperty.SLEEP_MODE,
    ),
    ThinQProperty.STYLER_OPERATION_MODE: SelectEntityDescription(
        key=ThinQProperty.STYLER_OPERATION_MODE,
        translation_key="operation_mode",
    ),
    ThinQProperty.WASHER_OPERATION_MODE: SelectEntityDescription(
        key=ThinQProperty.WASHER_OPERATION_MODE,
        translation_key="operation_mode",
    ),
}
REFRIGERATION_SELECT_DESC: dict[ThinQProperty, SelectEntityDescription] = {
    ThinQProperty.EXPRESS_MODE: SelectEntityDescription(
        key=ThinQProperty.EXPRESS_MODE,
        translation_key=ThinQProperty.EXPRESS_MODE,
    ),
    ThinQProperty.RAPID_FREEZE: SelectEntityDescription(
        key=ThinQProperty.RAPID_FREEZE,
        translation_key=ThinQProperty.RAPID_FREEZE,
    ),
}
WASHER_SELECTS: tuple[SelectEntityDescription, ...] = (
    OPERATION_SELECT_DESC[ThinQProperty.WASHER_OPERATION_MODE],
)
DEVICE_TYPE_SELECT_MAP: dict[DeviceType, tuple[SelectEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        SELECT_DESC[ThinQProperty.MONITORING_ENABLED],
        OPERATION_SELECT_DESC[ThinQProperty.AIR_CLEAN_OPERATION_MODE],
        SELECT_DESC[ThinQProperty.POWER_SAVE_ENABLED],
    ),
    DeviceType.AIR_PURIFIER_FAN: (
        AIR_FLOW_SELECT_DESC[ThinQProperty.WIND_STRENGTH],
        AIR_FLOW_SELECT_DESC[ThinQProperty.WIND_ANGLE],
        AIR_FLOW_SELECT_DESC[ThinQProperty.WARM_MODE],
        SELECT_DESC[ThinQProperty.DISPLAY_LIGHT],
        SELECT_DESC[ThinQProperty.CURRENT_JOB_MODE],
        SELECT_DESC[ThinQProperty.UV_NANO],
    ),
    DeviceType.AIR_PURIFIER: (
        AIR_FLOW_SELECT_DESC[ThinQProperty.WIND_STRENGTH],
        SELECT_DESC[ThinQProperty.CURRENT_JOB_MODE],
    ),
    DeviceType.DEHUMIDIFIER: (AIR_FLOW_SELECT_DESC[ThinQProperty.WIND_STRENGTH],),
    DeviceType.DISH_WASHER: (
        OPERATION_SELECT_DESC[ThinQProperty.DISH_WASHER_OPERATION_MODE],
    ),
    DeviceType.DRYER: (OPERATION_SELECT_DESC[ThinQProperty.DRYER_OPERATION_MODE],),
    DeviceType.HUMIDIFIER: (
        SELECT_DESC[ThinQPropertyEx.HUMIDITY_WARM_MODE],
        AIR_FLOW_SELECT_DESC[ThinQProperty.WIND_STRENGTH],
        SELECT_DESC[ThinQProperty.DISPLAY_LIGHT],
        SELECT_DESC[ThinQProperty.CURRENT_JOB_MODE],
        SELECT_DESC[ThinQProperty.MOOD_LAMP_STATE],
        OPERATION_SELECT_DESC[ThinQProperty.AUTO_MODE],
        OPERATION_SELECT_DESC[ThinQProperty.SLEEP_MODE],
        OPERATION_SELECT_DESC[ThinQProperty.HYGIENE_DRY_MODE],
    ),
    DeviceType.OVEN: (
        SELECT_DESC[ThinQProperty.COOK_MODE],
        OPERATION_SELECT_DESC[ThinQProperty.OVEN_OPERATION_MODE],
    ),
    DeviceType.REFRIGERATOR: (
        REFRIGERATION_SELECT_DESC[ThinQProperty.EXPRESS_MODE],
        REFRIGERATION_SELECT_DESC[ThinQProperty.RAPID_FREEZE],
    ),
    DeviceType.STYLER: (OPERATION_SELECT_DESC[ThinQProperty.STYLER_OPERATION_MODE],),
    DeviceType.SYSTEM_BOILER: (OPERATION_SELECT_DESC[ThinQProperty.HOT_WATER_MODE],),
    DeviceType.WASHCOMBO_MAIN: (
        OPERATION_SELECT_DESC[ThinQProperty.WASHER_OPERATION_MODE],
    ),
    DeviceType.WASHCOMBO_MINI: (
        OPERATION_SELECT_DESC[ThinQProperty.WASHER_OPERATION_MODE],
    ),
    DeviceType.WASHER: (OPERATION_SELECT_DESC[ThinQProperty.WASHER_OPERATION_MODE],),
    DeviceType.WASHTOWER_DRYER: (
        OPERATION_SELECT_DESC[ThinQProperty.WASHER_OPERATION_MODE],
    ),
    DeviceType.WASHTOWER: (
        OPERATION_SELECT_DESC[ThinQProperty.DRYER_OPERATION_MODE],
        OPERATION_SELECT_DESC[ThinQProperty.WASHER_OPERATION_MODE],
    ),
    DeviceType.WASHTOWER_WASHER: (
        OPERATION_SELECT_DESC[ThinQProperty.WASHER_OPERATION_MODE],
    ),
    DeviceType.WATER_HEATER: (SELECT_DESC[ThinQProperty.CURRENT_JOB_MODE],),
    DeviceType.WINE_CELLAR: (
        OPERATION_SELECT_DESC[ThinQProperty.LIGHT_BRIGHTNESS],
        OPERATION_SELECT_DESC[ThinQProperty.OPTIMAL_HUMIDITY],
    ),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for select platform."""
    entities: list[ThinQSelectEntity] = []
<<<<<<< HEAD
    for coordinator in entry.runtime_data.coordinators.values():
=======
    for coordinator in entry.runtime_data.values():
>>>>>>> Add select platform to LG ThinQ integration
        if (
            descriptions := DEVICE_TYPE_SELECT_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQSelectEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(
                        description.key, ActiveMode.WRITABLE
                    )
                )

    if entities:
        async_add_entities(entities)


class ThinQSelectEntity(ThinQEntity, SelectEntity):
    """Represent a thinq select platform."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: SelectEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize a select entity."""
        super().__init__(coordinator, entity_description, property_id)

        self._attr_options = self.data.options if self.data.options is not None else []

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        if self.data.value:
            self._attr_current_option = str(self.data.value)
        else:
            self._attr_current_option = None

        _LOGGER.debug(
            "[%s:%s] update status: %s -> %s, options:%s",
            self.coordinator.device_name,
            self.property_id,
            self.data.value,
            self.current_option,
            self.options,
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        _LOGGER.debug(
            "[%s:%s] async_select_option: %s",
            self.coordinator.device_name,
            self.property_id,
            option,
        )
        await self.async_call_api(self.coordinator.api.post(self.property_id, option))
