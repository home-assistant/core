"""Support for switches."""

from __future__ import annotations

from dataclasses import dataclass
from json.decoder import JSONDecodeError
from typing import Any, Final

from aiovodafone.const import WIFI_DATA, WifiBand, WifiType
from aiovodafone.exceptions import (
    AlreadyLogged,
    CannotAuthenticate,
    CannotConnect,
    GenericLoginError,
    GenericResponseError,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
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
        translation_key="main",
        band=WifiBand.BAND_2_4_GHZ,
        typology=WifiType.MAIN,
    ),
    VodafoneStationEntityDescription(
        key="guest",
        translation_key="guest",
        band=WifiBand.BAND_2_4_GHZ,
        typology=WifiType.GUEST,
    ),
    VodafoneStationEntityDescription(
        key="main_5g",
        translation_key="main_5g",
        band=WifiBand.BAND_5_GHZ,
        typology=WifiType.MAIN,
    ),
    VodafoneStationEntityDescription(
        key="guest_5g",
        translation_key="guest_5g",
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
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    async def _set_wifi_status(self, status: bool) -> None:
        """Set the wifi status."""
        try:
            await self.coordinator.api.set_wifi_status(
                status, self.entity_description.typology, self.entity_description.band
            )
        except CannotAuthenticate as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_authenticate",
                translation_placeholders={"error": repr(err)},
            ) from err
        except (
            CannotConnect,
            AlreadyLogged,
            GenericLoginError,
            GenericResponseError,
            JSONDecodeError,
        ) as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_execute_action",
                translation_placeholders={"error": repr(err)},
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_wifi_status(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_wifi_status(False)

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return bool(
            self.coordinator.data.wifi[WIFI_DATA][self.entity_description.key]["on"]
        )
