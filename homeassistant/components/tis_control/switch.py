"""Switch platform for integration_blueprint."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil
from typing import Any

from TISControlProtocol.BytesHelper import int_to_8_bit_binary
from TISControlProtocol.mock_api import TISApi
from TISControlProtocol.Protocols.udp.ProtocolHandler import (
    TISPacket,
    TISProtocolHandler,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import MATCH_ALL, STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TISConfigEntry

protocol_handler = TISProtocolHandler()


async def async_setup_entry(
    hass: HomeAssistant, entry: TISConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up the TIS switches."""
    # tis_api: TISApi = hass.data[DOMAIN]["tis_api"]
    tis_api: TISApi = entry.runtime_data.api
    # Fetch all switches from the TIS API we only have one type here
    switches: dict = await tis_api.get_entities(platform=Platform.SWITCH)
    if switches:
        # Prepare a list of tuples containing necessary switch details
        switch_entities = [
            (
                appliance_name,
                next(iter(appliance["channels"][0].values())),
                appliance["device_id"],
                appliance["is_protected"],
                appliance["gateway"],
            )
            for switch in switches
            for appliance_name, appliance in switch.items()
        ]
        # Create TISSwitch objects and add them to Home Assistant
        tis_switches = [
            TISSwitch(tis_api, switch_name, channel_number, device_id, gateway)
            for switch_name, channel_number, device_id, is_protected, gateway in switch_entities
        ]
        async_add_devices(tis_switches, update_before_add=True)


class TISSwitch(SwitchEntity):
    """Representation of a TIS switch."""

    def __init__(
        self,
        tis_api: TISApi,
        switch_name: str,
        channel_number: int,
        device_id: list[int],
        gateway: str,
    ) -> None:
        """Initialize the switch."""
        self.api = tis_api
        self._name = switch_name
        self._attr_unique_id = f"switch_{self.name}"
        self._state = STATE_UNKNOWN
        self._attr_is_on = None
        self.name = switch_name
        self.device_id = device_id
        self.gateway = gateway
        self.channel_number = int(channel_number)
        self.listener: Callable | None = None
        self.on_packet: TISPacket = protocol_handler.generate_control_on_packet(self)
        self.off_packet: TISPacket = protocol_handler.generate_control_off_packet(self)
        self.update_packet: TISPacket = protocol_handler.generate_control_update_packet(
            self
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""

        @callback
        async def handle_event(event: Event):
            """Handle the event."""
            # check if event is for this switch
            if event.event_type == str(self.device_id):
                if event.data["feedback_type"] == "control_response":
                    channel_value = event.data["additional_bytes"][2]
                    channel_number = event.data["channel_number"]
                    if int(channel_number) == self.channel_number:
                        self._state = (
                            STATE_ON if int(channel_value) == 100 else STATE_OFF
                        )
                elif event.data["feedback_type"] == "binary_feedback":
                    n_bytes = ceil(event.data["additional_bytes"][0] / 8)
                    channels_status = "".join(
                        int_to_8_bit_binary(event.data["additional_bytes"][i])
                        for i in range(1, n_bytes + 1)
                    )
                    self._state = (
                        STATE_ON
                        if channels_status[self.channel_number - 1] == "1"
                        else STATE_OFF
                    )
                elif event.data["feedback_type"] == "update_response":
                    additional_bytes = event.data["additional_bytes"]
                    channel_status = int(additional_bytes[self.channel_number])
                    self._state = STATE_ON if channel_status > 0 else STATE_OFF
                elif event.data["feedback_type"] == "offline_device":
                    self._state = STATE_UNKNOWN

            await self.async_update_ha_state(True)
            # self.schedule_update_ha_state()

        self.listener = self.hass.bus.async_listen(MATCH_ALL, handle_event)
        _ = await self.api.protocol.sender.send_packet(self.update_packet)

    async def async_will_remove_from_hass(self) -> None:
        """Remove the listener when the entity is removed."""
        self.listener = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        ack_status = await self.api.protocol.sender.send_packet_with_ack(
            self.on_packet,
        )
        if ack_status:
            self._state = STATE_ON
        else:
            self._state = STATE_UNKNOWN
            event_data = {
                "device_id": self.device_id,
                "feedback_type": "offline_device",
            }
            self.hass.bus.async_fire(str(self.device_id), event_data)
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        ack_status = await self.api.protocol.sender.send_packet_with_ack(
            self.off_packet
        )
        if ack_status:
            self._state = STATE_OFF
        else:
            self._state = STATE_UNKNOWN
        self.schedule_update_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the name of the switch."""
        self._name = value

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        if self._state == STATE_ON:
            return True

        elif self._state == STATE_OFF:  # noqa: RET505
            return False
        return False
