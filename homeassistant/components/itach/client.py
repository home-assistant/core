"""Client helpers for the legacy iTach remote platform."""

from pyitach import ItachClient, ItachError

from .command import ParsedItachCommand


def raw_timing_to_gc_cycles(duration_us: int, carrier_frequency: int) -> int:
    """Convert a raw microsecond timing to Global Caché carrier cycles."""
    return max(1, round(duration_us * carrier_frequency / 1_000_000))


def command_to_gc_timings(command: ParsedItachCommand) -> list[int]:
    """Convert parsed raw timings to Global Caché carrier-cycle timings."""
    return [
        raw_timing_to_gc_cycles(timing, command.modulation)
        for pair in command.get_raw_timings()
        for timing in (pair.high_us, pair.low_us)
    ]


async def async_create_client(host: str, port: int, timeout: float) -> ItachClient:
    """Create and connect a pyitach client."""
    client = ItachClient(host, port, timeout=timeout)
    try:
        await client.async_connect()
    except ItachError:
        await client.close()
        raise
    return client


async def async_send_command(
    client: ItachClient,
    module: int,
    connector: int,
    command: ParsedItachCommand,
    repeat: int,
) -> None:
    """Send a parsed legacy iTach command through pyitach."""
    await client.async_send_ir(
        module,
        connector,
        command.modulation,
        command_to_gc_timings(command),
        repeat=repeat,
    )
