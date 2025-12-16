"""Support for ESPHome infrared proxy remote components."""

from __future__ import annotations

from collections.abc import Iterable
from functools import partial
import json
import logging
from typing import Any

from aioesphomeapi import (
    EntityInfo,
    EntityState,
    InfraredProxyCapability,
    InfraredProxyInfo,
    InfraredProxyTimingParams,
)

from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN
from .entity import EsphomeEntity, platform_async_setup_entry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class EsphomeInfraredProxy(EsphomeEntity[InfraredProxyInfo, EntityState], RemoteEntity):
    """An infrared proxy remote implementation for ESPHome."""

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        capabilities = static_info.capabilities

        # Set supported features based on capabilities
        features = RemoteEntityFeature(0)
        if capabilities & InfraredProxyCapability.RECEIVER:
            features |= RemoteEntityFeature.LEARN_COMMAND
        self._attr_supported_features = features

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            # Infrared proxy entities should go available directly
            # when the device comes online.
            self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if remote is on."""
        # ESPHome infrared proxies are always on when available
        return self.available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the remote on."""
        # ESPHome infrared proxies are always on, nothing to do
        _LOGGER.debug("Turn on called for %s (no-op)", self.name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the remote off."""
        # ESPHome infrared proxies cannot be turned off
        _LOGGER.debug("Turn off called for %s (no-op)", self.name)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to a device.

        Commands should be JSON strings containing either:
        1. Protocol-based format: {"protocol": "NEC", "address": 0x04, "command": 0x08}
        2. Pulse-width format: {
            "timing": {
                "frequency": 38000,
                "length_in_bits": 32,
                "header_high_us": 9000,
                "header_low_us": 4500,
                ...
            },
            "data": [0x01, 0x02, 0x03, 0x04]
        }
        """
        self._check_capabilities()

        for cmd in command:
            try:
                cmd_data = json.loads(cmd)
            except json.JSONDecodeError as err:
                raise ServiceValidationError(
                    f"Command must be valid JSON: {err}"
                ) from err

            # Check if this is a protocol-based command
            if "protocol" in cmd_data:
                self._client.infrared_proxy_transmit_protocol(
                    self._static_info.key,
                    cmd,  # Pass the original JSON string
                )
            # Check if this is a pulse-width command
            elif "timing" in cmd_data and "data" in cmd_data:
                timing_data = cmd_data["timing"]
                data_array = cmd_data["data"]

                # Convert array of integers to bytes
                if not isinstance(data_array, list):
                    raise ServiceValidationError(
                        "Data must be an array of integers (0-255)"
                    )

                try:
                    data_bytes = bytes(data_array)
                except (ValueError, TypeError) as err:
                    raise ServiceValidationError(
                        f"Invalid data array: {err}. Each element must be an integer between 0 and 255."
                    ) from err

                timing = InfraredProxyTimingParams(
                    frequency=timing_data.get("frequency", 38000),
                    length_in_bits=timing_data.get("length_in_bits", 32),
                    header_high_us=timing_data.get("header_high_us", 0),
                    header_low_us=timing_data.get("header_low_us", 0),
                    one_high_us=timing_data.get("one_high_us", 0),
                    one_low_us=timing_data.get("one_low_us", 0),
                    zero_high_us=timing_data.get("zero_high_us", 0),
                    zero_low_us=timing_data.get("zero_low_us", 0),
                    footer_high_us=timing_data.get("footer_high_us", 0),
                    footer_low_us=timing_data.get("footer_low_us", 0),
                    repeat_high_us=timing_data.get("repeat_high_us", 0),
                    repeat_low_us=timing_data.get("repeat_low_us", 0),
                    minimum_idle_time_us=timing_data.get("minimum_idle_time_us", 0),
                    msb_first=timing_data.get("msb_first", True),
                    repeat_count=timing_data.get("repeat_count", 1),
                )
                self._client.infrared_proxy_transmit(
                    self._static_info.key,
                    timing,
                    data_bytes,
                )
            else:
                raise ServiceValidationError(
                    "Command must contain either 'protocol' or both 'timing' and 'data' fields"
                )

    def _check_capabilities(self) -> None:
        """Check if the device supports transmission."""
        if not self._static_info.capabilities & InfraredProxyCapability.TRANSMITTER:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="infrared_proxy_transmitter_not_supported",
            )

    async def async_learn_command(self, **kwargs: Any) -> None:
        """Learn a command from a device."""
        # Learning is handled through the receive event subscription
        # which is managed at the entry_data level
        raise HomeAssistantError(
            "Learning commands is handled automatically through receive events. "
            "Listen for esphome_infrared_proxy_received events instead."
        )


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=InfraredProxyInfo,
    entity_type=EsphomeInfraredProxy,
    state_type=EntityState,
)
