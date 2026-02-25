"""Switch platform for Compit integration."""

from dataclasses import dataclass
from typing import Any

from compit_inext_api.consts import CompitParameter

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CompitDeviceDescription:
    """Class to describe a Compit device."""

    name: str
    """Name of the device."""

    parameters: list[SwitchEntityDescription]
    """Parameters of the device."""


DESCRIPTIONS: dict[CompitParameter, SwitchEntityDescription] = {
    CompitParameter.HOLIDAY_MODE: SwitchEntityDescription(
        key=CompitParameter.HOLIDAY_MODE.value,
        translation_key="holiday_mode",
    ),
    CompitParameter.DEVICE_ON_OFF: SwitchEntityDescription(
        key=CompitParameter.DEVICE_ON_OFF.value,
        translation_key="device_on_off",
    ),
    CompitParameter.FORCE_DHW: SwitchEntityDescription(
        key=CompitParameter.FORCE_DHW.value,
        translation_key="force_dhw",
    ),
    CompitParameter.SUMMER_MODE: SwitchEntityDescription(
        key=CompitParameter.SUMMER_MODE.value,
        translation_key="summer_mode",
    ),
    CompitParameter.OUT_OF_HOME_MODE: SwitchEntityDescription(
        key=CompitParameter.OUT_OF_HOME_MODE.value,
        translation_key="out_of_home_mode",
    ),
    CompitParameter.PARTY_MODE: SwitchEntityDescription(
        key=CompitParameter.PARTY_MODE.value,
        translation_key="party_mode",
    ),
}

DEVICE_DEFINITIONS: dict[int, CompitDeviceDescription] = {
    5: CompitDeviceDescription(
        name="R350 T3",
        parameters=[DESCRIPTIONS[CompitParameter.SUMMER_MODE]],
    ),
    7: CompitDeviceDescription(
        name="Nano One",
        parameters=[DESCRIPTIONS[CompitParameter.HOLIDAY_MODE]],
    ),
    12: CompitDeviceDescription(
        name="Nano Color",
        parameters=[DESCRIPTIONS[CompitParameter.HOLIDAY_MODE]],
    ),
    36: CompitDeviceDescription(
        name="BioMax742",
        parameters=[DESCRIPTIONS[CompitParameter.SUMMER_MODE]],
    ),
    75: CompitDeviceDescription(
        name="BioMax772",
        parameters=[DESCRIPTIONS[CompitParameter.SUMMER_MODE]],
    ),
    92: CompitDeviceDescription(
        name="r490",
        parameters=[DESCRIPTIONS[CompitParameter.HOLIDAY_MODE]],
    ),
    201: CompitDeviceDescription(
        name="BioMax775",
        parameters=[DESCRIPTIONS[CompitParameter.SUMMER_MODE]],
    ),
    210: CompitDeviceDescription(
        name="EL750",
        parameters=[DESCRIPTIONS[CompitParameter.DEVICE_ON_OFF]],
    ),
    215: CompitDeviceDescription(
        name="R480",
        parameters=[
            DESCRIPTIONS[CompitParameter.HOLIDAY_MODE],
            DESCRIPTIONS[CompitParameter.SUMMER_MODE],
            DESCRIPTIONS[CompitParameter.PARTY_MODE],
        ],
    ),
    223: CompitDeviceDescription(
        name="Nano Color 2",
        parameters=[
            DESCRIPTIONS[CompitParameter.HOLIDAY_MODE],
            DESCRIPTIONS[CompitParameter.OUT_OF_HOME_MODE],
        ],
    ),
    224: CompitDeviceDescription(
        name="R 900",
        parameters=[
            DESCRIPTIONS[CompitParameter.HOLIDAY_MODE],
            DESCRIPTIONS[CompitParameter.FORCE_DHW],
        ],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Compit switch entities from a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        CompitSwitch(
            coordinator,
            device_id,
            device_definition.name,
            entity_description,
        )
        for device_id, device in coordinator.connector.all_devices.items()
        if (device_definition := DEVICE_DEFINITIONS.get(device.definition.code))
        for entity_description in device_definition.parameters
    )


class CompitSwitch(CoordinatorEntity[CompitDataUpdateCoordinator], SwitchEntity):
    """Representation of a Compit switch entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device_id: int,
        device_name: str,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device_name,
            manufacturer=MANUFACTURER_NAME,
            model=device_name,
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
        """Return the state of the switch."""
        value = self.coordinator.connector.get_current_option(
            self.device_id, CompitParameter(self.entity_description.key)
        )

        return True if value == STATE_ON else False if value == STATE_OFF else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.connector.select_device_option(
            self.device_id, CompitParameter(self.entity_description.key), STATE_ON
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.connector.select_device_option(
            self.device_id, CompitParameter(self.entity_description.key), STATE_OFF
        )
        self.async_write_ha_state()
