"""Support for EnOcean event entities."""

from enocean_async import EURID, EntityType, Gateway
from enocean_async.semantics.observation import Observable, Observation

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, LOGGER, SIGNAL_OBSERVATION
from .entity import NewEnOceanEntity


async def async_setup_platform(
    hass: HomeAssistant,
    _config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up EnOcean button event entities.

    Only accepts calls triggered via discovery from the binary_sensor platform;
    direct YAML configuration of this platform is not supported.
    """
    if discovery_info is None:
        return

    dev_id: list[int] = discovery_info[CONF_ID]

    try:
        eurid = EURID.from_bytelist(dev_id)
    except ValueError as err:
        LOGGER.error("Invalid device ID %s: %s", dev_id, err)
        return

    gateway: Gateway = hass.data.get(DOMAIN)
    if gateway is None:
        LOGGER.error("EnOcean gateway not found, cannot set up button events")
        return

    descriptor = gateway.device_descriptor(eurid)
    if descriptor is None:
        LOGGER.warning("No device descriptor found for device ID %s", dev_id)
        return

    entities = [
        EnOceanButtonEvent(eurid, entity.id)
        for entity in descriptor.entities
        if entity.entity_type == EntityType.PUSH_BUTTON
    ]
    add_entities(entities)


class EnOceanButtonEvent(NewEnOceanEntity, EventEntity):
    """An EnOcean rocker button represented as an event entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["pressed", "released", "clicked", "held"]

    async def async_added_to_hass(self) -> None:
        """Register observation callback when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_OBSERVATION, self._handle_observation
            )
        )

    @callback
    def _handle_observation(self, observation: Observation) -> None:
        """Handle an incoming observation and fire an event if it matches."""
        if observation.device_id != self.eurid:
            return
        if observation.entity_id != self.eep_entity_id:
            return

        push_button_value = observation.values.get(Observable.PUSH_BUTTON)
        if push_button_value not in self._attr_event_types:
            LOGGER.warning(
                "Received unsupported push button value '%s' for %s: %s",
                push_button_value,
                self.entity_id,
                observation,
            )
            return

        self._trigger_event(push_button_value)
        LOGGER.warning(
            f"Triggered event '{push_button_value}' for {self.entity_id} based on observation: {observation}"
        )
        self.async_write_ha_state()
