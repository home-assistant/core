"""Support for EnOcean switches."""

from typing import Any

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .entity import EnOceanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway = config_entry.runtime_data.gateway

    for entity_id in gateway.switch_entities:
        async_add_entities(
            [
                EnOceanSwitch(
                    entity_id,
                    gateway=gateway,
                )
            ]
        )


class EnOceanSwitch(EnOceanEntity, SwitchEntity):
    """Representation of EnOcean switches."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
        device_class: SwitchDeviceClass | None = SwitchDeviceClass.SWITCH,
    ) -> None:
        """Initialize the EnOcean switch."""
        super().__init__(enocean_entity_id=entity_id, gateway=gateway)
        self._attr_device_class = device_class
        self.gateway.register_switch_callback(self.enocean_entity_id, self.update)

    def update(self, is_on: bool) -> None:
        """Update the switch state."""
        self._attr_is_on = is_on
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self.gateway.switch_turn_on(self.enocean_entity_id)
        self._attr_is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self.gateway.switch_turn_off(self.enocean_entity_id)
        self._attr_is_on = False
        self.schedule_update_ha_state()
