"""Switch platform for integration_blueprint."""

from __future__ import annotations

from math import ceil
from typing import Any

from TISControlProtocol.BytesHelper import build_packet, int_to_8_bit_binary
from TISControlProtocol.mock_api import TISApi

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL, STATE_OFF, STATE_ON, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up the TIS switches."""
    tis_api: TISApi = hass.data[DOMAIN]["tis_api"]
    # Fetch all switches from the TIS API
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
        async_add_devices(tis_switches)


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
        self.name = switch_name
        self.device_id = device_id
        self.gateway = gateway
        self.channel_number = int(channel_number)
        self.listener = None
        self.on_packet = build_packet(
            operation_code=[0x00, 0x31],
            ip_address=self.api.host,
            destination_mac="FF:FF:FF:FF:FF:FF",
            device_id=self.device_id,
            additional_packets=[self.channel_number, 0x64, 0x00, 0x00],
        )
        self.off_packet = build_packet(
            operation_code=[0x00, 0x31],
            ip_address=self.api.host,
            destination_mac="FF:FF:FF:FF:FF:FF",
            device_id=self.device_id,
            additional_packets=[self.channel_number, 0x00, 0x00, 0x00],
        )
        self.update_packet = build_packet(
            operation_code=[0x00, 0x33],
            ip_address=self.api.host,
            destination_mac="FF:FF:FF:FF:FF:FF",
            device_id=self.device_id,
            additional_packets=[],
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
                        self._attr_state = (
                            STATE_ON if int(channel_value) == 100 else STATE_OFF
                        )
                elif event.data["feedback_type"] == "binary_feedback":
                    n_bytes = ceil(event.data["additional_bytes"][0] / 8)
                    channels_status = "".join(
                        int_to_8_bit_binary(event.data["additional_bytes"][i])
                        for i in range(1, n_bytes + 1)
                    )
                    self._attr_state = (
                        STATE_ON
                        if channels_status[self.channel_number - 1] == "1"
                        else STATE_OFF
                    )
                elif event.data["feedback_type"] == "update_response":
                    additional_bytes = event.data["additional_bytes"]
                    channel_status = int(additional_bytes[self.channel_number])
                    self._attr_state = STATE_ON if channel_status > 0 else STATE_OFF

            await self.async_update_ha_state(True)

        self.listener = self.hass.bus.async_listen(MATCH_ALL, handle_event)

    async def async_will_remove_from_hass(self) -> None:
        """Remove the listener when the entity is removed."""
        self.listener()
        self.listener = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        ack_status = await self.api.protocol.sender.send_packet_with_ack(
            self.gateway,
            self.on_packet,
            {"device_id": self.device_id, "operation_code": [0x00, 0x31]},
            self.channel_number,
        )
        if ack_status:
            self._attr_state = STATE_ON
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        ack_status = await self.api.protocol.sender.send_packet_with_ack(
            self.gateway,
            self.off_packet,
            {"device_id": self.device_id, "operation_code": [0x00, 0x31]},
            self.channel_number,
        )
        if ack_status:
            self._attr_state = STATE_OFF
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
        return self._attr_state == STATE_ON
