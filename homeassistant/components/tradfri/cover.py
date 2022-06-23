"""Support for IKEA Tradfri covers."""

from __future__ import annotations

from typing import Any

from pytradfri.api.aiocoap_api import APIRequestProtocol

from homeassistant.components.cover import ATTR_POSITION, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_GATEWAY_ID, DOMAIN
from .coordinator import TradfriDeviceDataUpdateCoordinator
from .entity import TradfriBaseEntity
from .models import TradfriData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Tradfri covers based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    tradfri_data: TradfriData = hass.data[DOMAIN][config_entry.entry_id]
    api = tradfri_data.api

    async_add_entities(
        TradfriCover(
            device_coordinator,
            api,
            gateway_id,
        )
        for device_coordinator in tradfri_data.coordinators
        if device_coordinator.device.has_blind_control
    )


class TradfriCover(TradfriBaseEntity, CoverEntity):
    """The platform class required by Home Assistant."""

    _attr_name = None

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        api: APIRequestProtocol,
        gateway_id: str,
    ) -> None:
        """Initialize a switch."""
        super().__init__(
            device_coordinator=device_coordinator,
            api=api,
            gateway_id=gateway_id,
        )

        device_control = self._device.blind_control
        assert device_control  # blind_control is ensured when creating the entity
        self._device_control = device_control
        self._device_data = device_control.blinds[0]

    def _refresh(self) -> None:
        """Refresh the device."""
        self._device_data = self._device_control.blinds[0]

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        return {"model": self._device.device_info.model_number}

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return 100 - self._device_data.current_cover_position

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self._api(self._device_control.set_state(100 - kwargs[ATTR_POSITION]))

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._api(self._device_control.set_state(0))

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._api(self._device_control.set_state(100))

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._api(self._device_control.trigger_blind())

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        return self.current_cover_position == 0
