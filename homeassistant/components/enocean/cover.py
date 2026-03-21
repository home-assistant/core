"""Support for EnOcean roller shutters."""

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
from .entity import EnOceanEntity, EnOceanEntityID

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
    gateway_eurid: EURID = await gateway.eurid

    entities = []
    for eurid, spec in gateway.device_specs.items():
        for entity in spec.entities:
            if entity.entity_type == EntityType.COVER:
                entity_id = EnOceanEntityID(device_address=eurid, unique_id=entity.id)
                entities.append(EnOceanCover(entity_id, gateway, gateway_eurid))

    async_add_entities(entities)


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
        enocean_entity_id: EnOceanEntityID,
        gateway: Gateway,
        gateway_eurid: EURID,
    ) -> None:
        """Initialize the EnOcean cover."""
        super().__init__(
            enocean_entity_id=enocean_entity_id,
            gateway=gateway,
            gateway_eurid=gateway_eurid,
        )
        self._attr_is_closed: bool | None = None
        gateway.add_observation_callback(self._on_observation)

    async def async_added_to_hass(self) -> None:
        """Query current position after Home Assistant (re)start."""
        await super().async_added_to_hass()
        await self.gateway.send_command(
            self.enocean_entity_id.device_address,
            CoverQueryPositionAndAngle(entity_id=self.enocean_entity_id.unique_id),
        )

    def _on_observation(self, observation: Observation) -> None:
        """Handle an incoming observation."""
        if (
            observation.device != self.enocean_entity_id.device_address
            or observation.entity != self.enocean_entity_id.unique_id
        ):
            return

        if Observable.COVER_STATE in observation.values:
            state = observation.values[Observable.COVER_STATE]
            is_opening, is_closing = _COVER_STATE_TO_HA.get(state, (False, False))
            self._attr_is_opening = is_opening
            self._attr_is_closing = is_closing
            self._attr_is_closed = state == "closed"

        if Observable.POSITION in observation.values:
            self._attr_current_cover_position = observation.values[Observable.POSITION]
            self._attr_is_closed = self._attr_current_cover_position == 0

        self.schedule_update_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.gateway.send_command(
            self.enocean_entity_id.device_address,
            CoverOpen(entity_id=self.enocean_entity_id.unique_id),
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.gateway.send_command(
            self.enocean_entity_id.device_address,
            CoverClose(entity_id=self.enocean_entity_id.unique_id),
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        if ATTR_POSITION not in kwargs:
            return
        await self.gateway.send_command(
            self.enocean_entity_id.device_address,
            CoverSetPositionAndAngle(
                position=kwargs[ATTR_POSITION],
                entity_id=self.enocean_entity_id.unique_id,
            ),
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop any cover movement."""
        await self.gateway.send_command(
            self.enocean_entity_id.device_address,
            CoverStop(entity_id=self.enocean_entity_id.unique_id),
        )
