"""Fan platform for Compit integration."""

from typing import Any

from compit_inext_api import PARAM_VALUES
from compit_inext_api.consts import CompitParameter

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

PARALLEL_UPDATES = 0

COMPIT_GEAR_TO_HA = PARAM_VALUES[CompitParameter.VENTILATION_GEAR_TARGET]
HA_STATE_TO_COMPIT = {value: key for key, value in COMPIT_GEAR_TO_HA.items()}


DEVICE_DEFINITIONS: dict[int, FanEntityDescription] = {
    223: FanEntityDescription(
        key="Nano Color 2",
        translation_key="ventilation",
    ),
    12: FanEntityDescription(
        key="Nano Color",
        translation_key="ventilation",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Compit fan entities from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        CompitFan(
            coordinator,
            device_id,
            device_definition,
        )
        for device_id, device in coordinator.connector.all_devices.items()
        if (device_definition := DEVICE_DEFINITIONS.get(device.definition.code))
    )


class CompitFan(CoordinatorEntity[CompitDataUpdateCoordinator], FanEntity):
    """Representation of a Compit fan entity."""

    _attr_speed_count = len(COMPIT_GEAR_TO_HA)
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
    )

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device_id: int,
        entity_description: FanEntityDescription,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=entity_description.key,
            manufacturer=MANUFACTURER_NAME,
            model=entity_description.key,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.connector.get_device(self.device_id) is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the fan is on."""
        value = self.coordinator.connector.get_current_option(
            self.device_id, CompitParameter.VENTILATION_ON_OFF
        )

        return True if value == STATE_ON else False if value == STATE_OFF else None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self.coordinator.connector.select_device_option(
            self.device_id, CompitParameter.VENTILATION_ON_OFF, STATE_ON
        )

        if percentage is None:
            self.async_write_ha_state()
            return

        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.connector.select_device_option(
            self.device_id, CompitParameter.VENTILATION_ON_OFF, STATE_OFF
        )
        self.async_write_ha_state()

    @property
    def percentage(self) -> int | None:
        """Return the current fan speed as a percentage."""
        if self.is_on is False:
            return 0
        mode = self.coordinator.connector.get_current_option(
            self.device_id, CompitParameter.VENTILATION_GEAR_TARGET
        )
        if mode is None:
            return None
        gear = COMPIT_GEAR_TO_HA.get(mode)
        return (
            None
            if gear is None
            else ordered_list_item_to_percentage(
                list(COMPIT_GEAR_TO_HA.values()),
                gear,
            )
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed."""
        if percentage == 0:
            await self.async_turn_off()
            return

        gear = int(
            percentage_to_ordered_list_item(
                list(COMPIT_GEAR_TO_HA.values()),
                percentage,
            )
        )
        mode = HA_STATE_TO_COMPIT.get(gear)
        if mode is None:
            return

        await self.coordinator.connector.select_device_option(
            self.device_id, CompitParameter.VENTILATION_GEAR_TARGET, mode
        )
        self.async_write_ha_state()
