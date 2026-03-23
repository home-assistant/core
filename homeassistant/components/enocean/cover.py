"""Support for EnOcean roller shutters."""

from asyncio import sleep
from typing import Any

from enocean_async import (
    EURID,
    CoverClose,
    CoverOpen,
    CoverQueryPositionAndAngle,
    CoverSetPositionAndAngle,
    CoverStop,
    EntityType,
    Gateway,
    Instructable,
    Observable,
    Observation,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnOceanConfigEntry
from .entity import EnOceanEntity

_COVER_STATE_TO_HA = {
    "opening": (True, False),
    "closing": (False, True),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data

    async_add_entities(
        EnOceanCover(
            eurid,
            entity.id,
            gateway,
            Instructable.COVER_QUERY_POSITION_AND_ANGLE in entity.actions,
        )
        for eurid, spec in gateway.device_specs.items()
        for entity in spec.entities
        if entity.entity_type == EntityType.COVER
    )


class EnOceanCover(EnOceanEntity, CoverEntity):
    """Representation of an EnOcean cover."""

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        address: EURID,
        entity_key: str,
        gateway: Gateway,
        supports_query: bool,
    ) -> None:
        """Initialize the EnOcean cover."""
        super().__init__(address, entity_key, gateway)
        self._supports_query = supports_query
        self._attr_is_closed: bool | None = None

    async def async_added_to_hass(self) -> None:
        """Query current position after Home Assistant (re)start."""
        await super().async_added_to_hass()
        if self._supports_query:
            # Schedule the query in the background to avoid delaying HA startup.
            self.hass.async_create_task(self._async_query_position_later())

    async def _async_query_position_later(self) -> None:
        """Wait for the gateway to be ready, then query current position."""
        await sleep(5)  # Wait a bit for the gateway to be ready after HA startup.
        await self.gateway.send_command(
            self.address,
            CoverQueryPositionAndAngle(entity_id=self.entity_key),
        )

    def _update_from_observation(self, observation: Observation) -> None:
        """Handle an incoming observation."""
        if Observable.COVER_STATE in observation.values:
            state = observation.values[Observable.COVER_STATE]
            is_opening, is_closing = _COVER_STATE_TO_HA.get(state, (False, False))
            self._attr_is_opening = is_opening
            self._attr_is_closing = is_closing
            self._attr_is_closed = state == "closed"

        if Observable.POSITION in observation.values:
            # HA: 0=closed, 100=open. Library: 0=open, 100=closed.
            self._attr_current_cover_position = (
                100 - observation.values[Observable.POSITION]
            )
            self._attr_is_closed = self._attr_current_cover_position == 0

        self.async_write_ha_state()

    async def async_open_cover(self, **_kwargs: Any) -> None:
        """Open the cover."""
        await self.gateway.send_command(
            self.address, CoverOpen(entity_id=self.entity_key)
        )

    async def async_close_cover(self, **_kwargs: Any) -> None:
        """Close the cover."""
        await self.gateway.send_command(
            self.address, CoverClose(entity_id=self.entity_key)
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        if ATTR_POSITION not in kwargs:
            return
        await self.gateway.send_command(
            self.address,
            CoverSetPositionAndAngle(
                # HA: 0=closed, 100=open. Library: 0=open, 100=closed.
                position=100 - kwargs[ATTR_POSITION],
                entity_id=self.entity_key,
            ),
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop any cover movement."""
        await self.gateway.send_command(
            self.address, CoverStop(entity_id=self.entity_key)
        )
