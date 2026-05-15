"""Infrared entities for Global Caché iTach IP2IR."""

import logging

from homeassistant.components.infrared import InfraredEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ItachConfigEntry
from .const import DOMAIN
from .infrared_compat import InfraredCommand
from .pyitach import (
    ItachBusyError,
    ItachClient,
    ItachCommandError,
    ItachConnectionError,
    ItachResponseError,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ItachConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IR emitter entities for configured iTach IR output ports."""
    data = entry.runtime_data

    async_add_entities(
        [
            ItachInfraredEntity(
                host=data.host,
                device_id=data.device_id,
                ir_module=data.ir_module,
                ir_port=ir_port,
                mode=data.ir_connector_modes.get(str(ir_port), "IR"),
                client=data.client,
            )
            for ir_port in data.ir_enabled_ports
        ],
        update_before_add=False,
    )


def _device_connections(device_id: str) -> set[tuple[str, str]]:
    """Return device connections for a canonical Global Caché device ID."""
    if device_id.startswith("GlobalCache_") and len(device_id) == 24:
        raw_mac = device_id.removeprefix("GlobalCache_")
        if len(raw_mac) == 12:
            mac = ":".join(raw_mac[index : index + 2] for index in range(0, 12, 2))
            return {("mac", mac)}

    return set()


class ItachInfraredEntity(InfraredEntity):
    """Represents one IR output port of the iTach device."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        host: str,
        device_id: str,
        ir_module: int,
        ir_port: int,
        mode: str,
        client: ItachClient,
    ) -> None:
        """Initialize the IR entity."""
        self._host = host
        self._device_id = device_id
        self._ir_module = ir_module
        self._ir_port = ir_port
        self._mode = mode
        self._client = client

        self._attr_translation_key = (
            "ir_blaster_port" if mode == "IR_BLASTER" else "ir_port"
        )
        self._attr_translation_placeholders = {"port": str(ir_port)}
        self._attr_unique_id = f"{device_id}_port_{ir_port}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for Home Assistant device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            connections=_device_connections(self._device_id),
            name=f"iTach IP2IR ({self._host})",
            manufacturer="Global Caché",
            model="iTach IP2IR",
            configuration_url=f"http://{self._host}",
        )

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command via the iTach."""
        try:
            carrier_frequency = int(command.modulation)
            timings = self._command_to_gc_timings(command, carrier_frequency)
        except (TypeError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="itach_invalid_command",
                translation_placeholders={"error": str(err)},
            ) from err

        try:
            await self._client.async_send_ir(
                self._ir_module,
                self._ir_port,
                carrier_frequency,
                timings,
            )
        except ItachBusyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="itach_busy",
            ) from err
        except (ItachCommandError, ItachResponseError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="itach_rejected_command",
                translation_placeholders={"error": str(err)},
            ) from err
        except ItachConnectionError as err:
            if self._attr_available:
                _LOGGER.warning(
                    "Lost connection to iTach %s while sending IR on port %s",
                    self._host,
                    self._ir_port,
                )
                self._attr_available = False
                self.async_write_ha_state()

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="itach_connection_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        if not self._attr_available:
            _LOGGER.info(
                "Connection to iTach %s recovered while sending IR on port %s",
                self._host,
                self._ir_port,
            )
            self._attr_available = True
            self.async_write_ha_state()

    def _command_to_gc_timings(
        self,
        command: InfraredCommand,
        carrier_frequency: int,
    ) -> list[int]:
        """Convert an HA InfraredCommand to Global Caché cycle timings."""
        if carrier_frequency <= 0:
            raise ValueError("Carrier frequency must be greater than zero")

        timings: list[int] = []

        for timing in command.get_raw_timings():
            for duration_us in (timing.high_us, timing.low_us):
                if duration_us <= 0:
                    raise ValueError("IR timing durations must be greater than zero")

                cycles = max(1, round(duration_us * carrier_frequency / 1_000_000))
                timings.append(cycles)

        if len(timings) % 2 != 0:
            raise ValueError("IR command contains an unmatched mark without a gap")

        if not timings:
            raise ValueError("IR command contains no usable raw timings")

        return timings
