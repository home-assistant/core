"""Support for Tasmota infrared emitters."""

from hatasmota.entity import TasmotaEntity as HATasmotaEntity
from hatasmota.infrared import (
    TasmotaIRSendCommand,
    TasmotaIRSendRawTimingsCommand,
    TasmotaInfraredEmitter,
)
from hatasmota.models import DiscoveryHashType
from infrared_protocols.commands import Command as InfraredCommand
from infrared_protocols.commands.nec import NECCommand
from infrared_protocols.commands.samsung import Samsung32Command

from homeassistant.components import infrared
from homeassistant.components.infrared import InfraredEmitterEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_REMOVE_DISCOVER_COMPONENT, DOMAIN
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .entity import TasmotaAvailability, TasmotaDiscoveryUpdate, TasmotaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tasmota infrared dynamically through discovery."""

    @callback
    def async_discover(
        tasmota_entity: HATasmotaEntity, discovery_hash: DiscoveryHashType
    ) -> None:
        """Discover and add a Tasmota infrared emitter."""
        async_add_entities(
            [
                TasmotaInfraredEmitterEntity(
                    tasmota_entity=tasmota_entity, discovery_hash=discovery_hash
                )
            ]
        )

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(infrared.DOMAIN)] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_ENTITY_NEW.format(infrared.DOMAIN),
            async_discover,
        )
    )


def _nec_to_irsend(command: NECCommand) -> TasmotaIRSendCommand:
    """Convert a NECCommand to compact Tasmota IRSend form.

    Tasmota Data is MSB-first: byte3 byte2 byte1 byte0 as a 32-bit hex value.
    Standard NEC (8-bit address): address | ~address | command | ~command.
    Extended NEC (16-bit address): addr_high | addr_low | command | ~command.
    Both map to protocol "NEC" in Tasmota/IRremoteESP8266.
    """
    if command.address <= 0xFF:
        byte3 = command.address & 0xFF
        byte2 = (~command.address) & 0xFF
    else:
        byte3 = (command.address >> 8) & 0xFF
        byte2 = command.address & 0xFF

    byte1 = command.command & 0xFF
    byte0 = (~command.command) & 0xFF

    data = (byte3 << 24) | (byte2 << 16) | (byte1 << 8) | byte0

    send_times = command.repeat_count + 1 if command.repeat_count > 0 else None
    return TasmotaIRSendCommand(
        protocol="NEC",
        bits=32,
        data=f"0x{data:08X}",
        send_times=send_times,
    )


def _samsung32_to_irsend(command: Samsung32Command) -> TasmotaIRSendCommand:
    """Convert a Samsung32Command to compact Tasmota IRSend form.

    Tasmota Data is MSB-first. Samsung-32 repeats the address byte (unlike NEC
    which inverts it), then command | ~command.
    """
    if command.address <= 0xFF:
        # Samsung-32 repeats the address byte (unlike NEC which inverts it).
        byte3 = command.address & 0xFF
        byte2 = command.address & 0xFF
    else:
        byte3 = (command.address >> 8) & 0xFF
        byte2 = command.address & 0xFF

    byte1 = command.command & 0xFF
    byte0 = (~command.command) & 0xFF

    data = (byte3 << 24) | (byte2 << 16) | (byte1 << 8) | byte0

    send_times = command.repeat_count + 1 if command.repeat_count > 0 else None
    return TasmotaIRSendCommand(
        protocol="SAMSUNG",
        bits=32,
        data=f"0x{data:08X}",
        send_times=send_times,
    )


def _to_raw_timings(command: InfraredCommand) -> TasmotaIRSendRawTimingsCommand:
    """Convert any InfraredCommand to raw timings IRSend form.

    infrared_protocols uses signed ints: positive=mark (high), negative=space (low).
    Tasmota raw timings are absolute values, alternating mark/space.
    """
    modulation = command.modulation
    if modulation is not None and (not isinstance(modulation, int) or modulation < 0):
        raise ValueError(
            f"Command modulation must be a non-negative integer, got {modulation!r}"
        )
    timings = tuple(abs(t) for t in command.get_raw_timings())
    # infrared_protocols already encodes repeats inside the timing stream,
    # so send_times would double-repeat — always send once at the raw level.
    return TasmotaIRSendRawTimingsCommand(
        frequency=modulation,
        timings=timings,
    )


class TasmotaInfraredEmitterEntity(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    TasmotaEntity,
    InfraredEmitterEntity,
):
    """Representation of a Tasmota infrared emitter."""

    _tasmota_entity: TasmotaInfraredEmitter

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command via Tasmota."""
        try:
            if isinstance(command, NECCommand):
                await self._tasmota_entity.send_irsend(_nec_to_irsend(command))
            elif isinstance(command, Samsung32Command):
                await self._tasmota_entity.send_irsend(_samsung32_to_irsend(command))
            else:
                await self._tasmota_entity.send_irsend_raw(_to_raw_timings(command))
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
