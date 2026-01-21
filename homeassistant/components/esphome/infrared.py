"""Infrared platform for ESPHome."""

from __future__ import annotations

from functools import partial
import logging

from aioesphomeapi import EntityInfo, EntityState, InfraredCapability, InfraredInfo

from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEntity,
    InfraredEntityFeature,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import EsphomeEntity, platform_async_setup_entry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class EsphomeInfraredEntity(EsphomeEntity[InfraredInfo, EntityState], InfraredEntity):
    """ESPHome infrared entity using native API."""

    _attr_has_entity_name = True

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        capabilities = static_info.capabilities

        features = InfraredEntityFeature(0)
        if capabilities & InfraredCapability.TRANSMITTER:
            features |= InfraredEntityFeature.TRANSMIT
        if capabilities & InfraredCapability.RECEIVER:
            features |= InfraredEntityFeature.RECEIVE
        self._attr_supported_features = features

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
        has_transmit = bool(self.supported_features & InfraredEntityFeature.TRANSMIT)
        has_receive = bool(self.supported_features & InfraredEntityFeature.RECEIVE)
        if has_transmit and has_receive:
            return "IR Transceiver"
        if has_transmit:
            return "IR Transmitter"
        if has_receive:
            return "IR Receiver"
        raise HomeAssistantError("Invalid infrared entity with no supported features.")

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command.

        Raises:
            HomeAssistantError: If transmission fails or not supported.
        """
        if not self._static_info.capabilities & InfraredCapability.TRANSMITTER:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="infrared_proxy_transmitter_not_supported",
            )

        timings = [
            interval
            for timing in command.get_raw_timings()
            for interval in (timing.high_us, -timing.low_us)
        ]
        _LOGGER.debug("Sending command: %s", timings)

        try:
            self._client.infrared_rf_transmit_raw_timings(
                self._static_info.key, carrier_frequency=38000, timings=timings
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
    info_type=InfraredInfo,
    entity_type=EsphomeInfraredEntity,
    state_type=EntityState,
)
