"""Support for Synology DSM switch."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from synology_dsm.api.surveillance_station import SynoSurveillanceStation

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SynoApi
from .const import DOMAIN
from .coordinator import SynologyDSMConfigEntry, SynologyDSMSwitchUpdateCoordinator
from .entity import SynologyDSMBaseEntity, SynologyDSMEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SynologyDSMSwitchEntityDescription(
    SwitchEntityDescription, SynologyDSMEntityDescription
):
    """Describes Synology DSM switch entity."""


SURVEILLANCE_SWITCH: tuple[SynologyDSMSwitchEntityDescription, ...] = (
    SynologyDSMSwitchEntityDescription(
        api_key=SynoSurveillanceStation.HOME_MODE_API_KEY,
        key="home_mode",
        translation_key="home_mode",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SynologyDSMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Synology NAS switch."""
    data = entry.runtime_data
    if coordinator := data.coordinator_switches:
        assert coordinator.version is not None
        async_add_entities(
            SynoDSMSurveillanceHomeModeToggle(
                data.api, coordinator.version, coordinator, description
            )
            for description in SURVEILLANCE_SWITCH
        )


class SynoDSMSurveillanceHomeModeToggle(
    SynologyDSMBaseEntity[SynologyDSMSwitchUpdateCoordinator], SwitchEntity
):
    """Representation a Synology Surveillance Station Home Mode toggle."""

    entity_description: SynologyDSMSwitchEntityDescription

    def __init__(
        self,
        api: SynoApi,
        version: str,
        coordinator: SynologyDSMSwitchUpdateCoordinator,
        description: SynologyDSMSwitchEntityDescription,
    ) -> None:
        """Initialize a Synology Surveillance Station Home Mode."""
        super().__init__(api, coordinator, description)
        self._version = version

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self.coordinator.data["switches"][self.entity_description.key]  # type: ignore[no-any-return]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Home mode."""
        assert self._api.surveillance_station is not None
        assert self._api.information
        _LOGGER.debug(
            "SynoDSMSurveillanceHomeModeToggle.turn_on(%s)",
            self._api.information.serial,
        )
        await self._api.dsm.surveillance_station.set_home_mode(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Home mode."""
        assert self._api.surveillance_station is not None
        assert self._api.information
        _LOGGER.debug(
            "SynoDSMSurveillanceHomeModeToggle.turn_off(%s)",
            self._api.information.serial,
        )
        await self._api.dsm.surveillance_station.set_home_mode(False)
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.surveillance_station) and super().available

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        assert self._api.surveillance_station is not None
        assert self._api.information is not None
        assert self._api.network is not None
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self._api.information.serial}_{SynoSurveillanceStation.INFO_API_KEY}",
                )
            },
            name=f"{self._api.network.hostname} Surveillance Station",
            manufacturer="Synology",
            model=self._api.information.model,
            sw_version=self._version,
            via_device=(DOMAIN, self._api.information.serial),
        )
