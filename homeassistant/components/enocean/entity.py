"""Representation of an EnOcean device."""

from enocean_async import EURID, Gateway, Observation
from enocean_async.semantics.entity import EntityCategory as LibEntityCategory

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_OBSERVATION

LIB_ENTITY_CATEGORY_MAP: dict[str, EntityCategory | None] = {
    LibEntityCategory.CONFIG: EntityCategory.CONFIG,
    LibEntityCategory.DIAGNOSTIC: EntityCategory.DIAGNOSTIC,
    LibEntityCategory.DEFAULT: None,
}


class EnOceanEntity(Entity):
    """Parent class for all entities associated with the EnOcean component."""

    def __init__(
        self,
        address: EURID,
        entity_key: str,
        gateway: Gateway,
    ) -> None:
        """Initialize the entity."""
        super().__init__()

        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._attr_translation_key = entity_key
        self._attr_unique_id = f"{address}.{entity_key}"

        self.address: EURID = address
        self.entity_key: str = entity_key
        self.gateway: Gateway = gateway

    async def async_added_to_hass(self) -> None:
        """Subscribe to gateway observations."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_OBSERVATION, self._on_observation
            )
        )

    @callback
    def _on_observation(self, observation: Observation) -> None:
        """Filter and dispatch incoming observations."""
        if observation.device != self.address or observation.entity != self.entity_key:
            return
        self._update_from_observation(observation)

    def _update_from_observation(self, _observation: Observation) -> None:
        """Update entity state from a matched observation (override in subclasses)."""

    @property
    def device_info(self) -> DeviceInfo | None:
        """Get device info."""
        gateway_eurid = self.gateway.eurid
        if self.address == gateway_eurid:
            return DeviceInfo(identifiers={(DOMAIN, str(gateway_eurid))})
        spec = self.gateway.device_spec(self.address)
        if spec is None:
            return None

        dt = spec.device_type
        manufacturer = str(dt.manufacturer) if dt.manufacturer is not None else None

        return DeviceInfo(
            identifiers={(DOMAIN, str(self.address))},
            manufacturer=manufacturer,
            model=dt.model,
            model_id=f"EEP {dt.eep}",
            serial_number=str(self.address),
            via_device=(DOMAIN, str(gateway_eurid)),
        )
