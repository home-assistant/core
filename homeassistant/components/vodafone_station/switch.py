"""Support for switches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aiovodafone.const import WIFI_DATA, WifiBand, WifiType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VodafoneConfigEntry, VodafoneStationRouter

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VodafoneStationEntityDescription(SwitchEntityDescription):
    """Vodafone Station entity description."""

    band: WifiBand
    typology: WifiType


SWITCHES: Final = (
    VodafoneStationEntityDescription(
        key="main",
        band=WifiBand.BAND_2_4_GHZ,
        typology=WifiType.MAIN,
    ),
    VodafoneStationEntityDescription(
        key="guest",
        band=WifiBand.BAND_2_4_GHZ,
        typology=WifiType.GUEST,
        icon="mdi:wifi-guest",
    ),
    VodafoneStationEntityDescription(
        key="main_5g",
        band=WifiBand.BAND_5_GHZ,
        typology=WifiType.MAIN,
    ),
    VodafoneStationEntityDescription(
        key="guest_5g",
        band=WifiBand.BAND_5_GHZ,
        typology=WifiType.GUEST,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VodafoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vodafone Station switches based on a config entry."""

    coordinator = entry.runtime_data

    wifi = coordinator.data.wifi

    async_add_entities(
        VodafoneSwitchEntity(coordinator, switch_desc)
        for switch_desc in SWITCHES
        if switch_desc.key in wifi[WIFI_DATA]
    )


class VodafoneSwitchEntity(CoordinatorEntity[VodafoneStationRouter], SwitchEntity):
    """Switch device."""

    _attr_has_entity_name = True
    entity_description: VodafoneStationEntityDescription

    def __init__(
        self,
        coordinator: VodafoneStationRouter,
        description: VodafoneStationEntityDescription,
    ) -> None:
        """Initialize switch device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_name = coordinator.data.wifi[WIFI_DATA][description.key]["ssid"]
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.api.set_wifi_status(
            True, self.entity_description.typology, self.entity_description.band
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.api.set_wifi_status(
            False, self.entity_description.typology, self.entity_description.band
        )

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return bool(
            self.coordinator.data.wifi[WIFI_DATA][self.entity_description.key]["on"]
        )
