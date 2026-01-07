"""Infrared platform for ESPHome."""

from __future__ import annotations

from functools import partial
import json
import logging

from aioesphomeapi import (
    EntityInfo,
    EntityState,
    InfraredProxyCapability,
    InfraredProxyInfo,
    InfraredProxyTimingParams,
)

from homeassistant.components.infrared import (
    PULSE_WIDTH_COMPAT_PROTOCOLS,
    InfraredCommand,
    InfraredEntity,
    InfraredEntityFeature,
    InfraredProtocolType,
    NECInfraredCommand,
    PulseWidthInfraredCommand,
    SamsungInfraredCommand,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import EsphomeEntity, platform_async_setup_entry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class EsphomeInfraredEntity(
    EsphomeEntity[InfraredProxyInfo, EntityState], InfraredEntity
):
    """ESPHome infrared entity using native API."""

    _attr_has_entity_name = True

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        capabilities = static_info.capabilities

        features = InfraredEntityFeature(0)
        if capabilities & InfraredProxyCapability.TRANSMITTER:
            features |= InfraredEntityFeature.TRANSMIT
        if capabilities & InfraredProxyCapability.RECEIVER:
            features |= InfraredEntityFeature.RECEIVE
        self._attr_supported_features = features

        if capabilities & InfraredProxyCapability.TRANSMITTER:
            self._attr_supported_protocols = {
                InfraredProtocolType.PULSE_WIDTH,
                InfraredProtocolType.NEC,
                InfraredProtocolType.SAMSUNG,
            }
        else:
            self._attr_supported_protocols = set()

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            # Infrared entities should go available as soon as the device comes online
            self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the infrared entity."""
        if self.supported_features & InfraredEntityFeature.TRANSMIT:
            return "IR Transmitter"
        if self.supported_features & InfraredEntityFeature.RECEIVE:
            return "IR Receiver"
        return "IR Transceiver"

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command.

        Raises:
            HomeAssistantError: If transmission fails or not supported.
        """
        if not self._static_info.capabilities & InfraredProxyCapability.TRANSMITTER:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="infrared_proxy_transmitter_not_supported",
            )

        if isinstance(command, (NECInfraredCommand, SamsungInfraredCommand)):
            await self._async_send_protocol_command(command)
        else:
            # Fall back to pulse-width transmission if the protocol is compatible
            await self._async_send_pulse_width_command(command)

    async def _async_send_protocol_command(self, command: InfraredCommand) -> None:
        """Send command using protocol-specific arguments."""
        if isinstance(command, NECInfraredCommand):
            cmd_json = json.dumps(
                {
                    "protocol": "nec",
                    "address": command.address,
                    "command": command.command,
                    "repeat": command.repeat_count,
                }
            )
        elif isinstance(command, SamsungInfraredCommand):
            cmd_json = json.dumps(
                {
                    "protocol": "samsung",
                    "data": command.code,
                    "nbits": command.length_in_bits,
                    "repeat": command.repeat_count,
                }
            )
        else:
            raise HomeAssistantError(
                f"Unsupported protocol command type: {type(command)}"
            )

        _LOGGER.debug("Sending command: %s", cmd_json)

        try:
            self._client.infrared_proxy_transmit_protocol(
                self._static_info.key, cmd_json
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_sending_ir_command",
                translation_placeholders={
                    "device_name": self._device_info.name,
                    "error": str(err),
                },
            ) from err

    async def _async_send_pulse_width_command(self, command: InfraredCommand) -> None:
        """Send command using the pulse-width generic protocol."""
        if isinstance(command, PulseWidthInfraredCommand):
            protocol = command.protocol
            code = command.code
            length_in_bits = command.length_in_bits
        elif command.protocol.type in PULSE_WIDTH_COMPAT_PROTOCOLS:
            compat_protocol_method = getattr(
                command.protocol, "get_pulse_width_compat_protocol", None
            )
            compat_code_method = getattr(command, "get_pulse_width_compat_code", None)
            protocol = compat_protocol_method()  # type: ignore[misc]
            code = compat_code_method()  # type: ignore[misc]
            length_in_bits = 32
        else:
            raise HomeAssistantError(f"Unsupported command type: {type(command)}")

        num_bytes = (length_in_bits + 7) // 8
        data_bytes = code.to_bytes(
            num_bytes, byteorder="big" if protocol.msb_first else "little"
        )

        timing = InfraredProxyTimingParams(
            frequency=protocol.frequency,
            length_in_bits=length_in_bits,
            header_high_us=protocol.header.high_us,
            header_low_us=protocol.header.low_us,
            one_high_us=protocol.one.high_us,
            one_low_us=protocol.one.low_us,
            zero_high_us=protocol.zero.high_us,
            zero_low_us=protocol.zero.low_us,
            footer_high_us=protocol.footer.high_us,
            footer_low_us=protocol.footer.low_us,
            repeat_high_us=0,
            repeat_low_us=0,
            minimum_idle_time_us=protocol.minimum_idle_time_us,
            msb_first=protocol.msb_first,
            repeat_count=command.repeat_count,
        )

        _LOGGER.debug(
            "Sending pulse-width command via native API: timing=%s, data=%s",
            timing,
            data_bytes.hex(),
        )

        try:
            self._client.infrared_proxy_transmit(
                self._static_info.key, timing, data_bytes
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_sending_ir_command",
                translation_placeholders={
                    "device_name": self._device_info.name,
                    "error": str(err),
                },
            ) from err


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=InfraredProxyInfo,
    entity_type=EsphomeInfraredEntity,
    state_type=EntityState,
)
