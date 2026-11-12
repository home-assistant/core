"""Home Assistant integration module for Greencell EVSE charging control over MQTT."""

import json
from typing import Any, override

from greencell_client.access import GreencellAccess
from greencell_client.state import EvseStateData

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SERIAL_NUMBER, DOMAIN
from .entity import GreencellEntity
from .models import GreencellConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreencellConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Greencell EVSE charging switch from a config entry."""
    async_add_entities(
        [
            GreencellChargingSwitch(
                entry.data[CONF_SERIAL_NUMBER], entry.runtime_data.access
            )
        ]
    )


class GreencellChargingSwitch(GreencellEntity, SwitchEntity):
    """Switch that starts and stops charging on a Greencell EVSE."""

    _attr_should_poll = False
    _attr_translation_key = "charging"

    def __init__(self, serial_number: str, access: GreencellAccess) -> None:
        """Initialize the charging switch."""
        super().__init__(serial_number, access)
        self._evse_state = EvseStateData()
        self._status_topic = f"/greencell/evse/{serial_number}/status"
        self._cmd_topic = f"/greencell/evse/{serial_number}/cmd"
        self._attr_unique_id = f"{serial_number}_charging"

    @override
    async def async_added_to_hass(self) -> None:
        """Register the entity with Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            await mqtt.async_subscribe(
                self.hass, self._status_topic, self._status_message_received
            )
        )

    @callback
    def _status_message_received(self, msg: ReceiveMessage) -> None:
        """Track the charging state reported by the device."""
        try:
            data = json.loads(msg.payload)
        except ValueError, TypeError:
            return
        if isinstance(data, dict) and isinstance(state := data.get("state"), str):
            self._evse_state.update(state)
            self._attr_is_on = self._evse_state.can_be_stopped()
            self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging."""
        await self._async_send_command("START")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging."""
        await self._async_send_command("STOP")

    async def _async_send_command(self, name: str) -> None:
        """Publish a command to the device."""
        if not self._access.can_execute():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="execute_not_allowed",
            )
        await mqtt.async_publish(self.hass, self._cmd_topic, json.dumps({"name": name}))
