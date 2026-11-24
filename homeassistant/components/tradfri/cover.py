"""Support for IKEA Tradfri covers."""

from typing import TYPE_CHECKING, Any, override

from pytradfri.api.aiocoap_api import APIRequestProtocol

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_GATEWAY_ID
from .coordinator import TradfriConfigEntry, TradfriDeviceDataUpdateCoordinator
from .entity import TradfriBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TradfriConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load Tradfri covers based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    tradfri_data = config_entry.runtime_data

    async_add_entities(
        TradfriCover(
            device_coordinator,
            tradfri_data.api,
            gateway_id,
        )
        for device_coordinator in tradfri_data.coordinator_list
        if device_coordinator.device.has_blind_control
    )


class TradfriCover(TradfriBaseEntity, CoverEntity):
    """The platform class required by Home Assistant."""

    _attr_name = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

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

        if TYPE_CHECKING:
            assert self._device.blind_control is not None
        self._device_control = self._device.blind_control
        self._device_data = self._device_control.blinds[0]

    @callback
    @override
    def _refresh(self) -> None:
        """Refresh the device."""
        self._device_data = self._device_control.blinds[0]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        return {"model": self._device.device_info.model_number}

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = self._device_data.current_cover_position
        return None if position is None else 100 - position

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self._api(self._device_control.set_state(100 - kwargs[ATTR_POSITION]))

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._api(self._device_control.set_state(0))

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._api(self._device_control.set_state(100))

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._api(self._device_control.trigger_blind())

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        position = self.current_cover_position
        return None if position is None else position == 0
