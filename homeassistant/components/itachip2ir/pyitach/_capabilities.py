"""iTach hardware capability helpers."""

from dataclasses import dataclass

from ._client import ItachClient

IR_OUTPUT_MODES = frozenset({"IR", "IR_BLASTER"})


@dataclass(frozen=True, slots=True)
class ItachIrCapability:
    """Current iTach infrared module and connector capability."""

    module: int
    ports: int
    enabled_ports: list[int]
    connector_modes: dict[str, str]


def enabled_ir_ports(
    connector_modes: dict[int, str],
    ir_ports: int,
) -> list[int]:
    """Return currently IR-capable connectors.

    If connector mode probing returns no data, older firmware may not support
    get_IR. In that case, fall back to every connector reported by getdevices.
    """
    enabled_ports = [
        connector
        for connector, mode in connector_modes.items()
        if mode in IR_OUTPUT_MODES
    ]
    if enabled_ports or connector_modes:
        return enabled_ports
    return list(range(1, ir_ports + 1))


def enabled_ir_ports_with_fallback(
    connector_modes: dict[int, str],
    ir_ports: int,
) -> tuple[list[int], dict[str, str]]:
    """Return IR-capable connectors and serializable connector modes."""
    enabled_ports = [
        connector
        for connector, mode in connector_modes.items()
        if mode in IR_OUTPUT_MODES
    ]

    if enabled_ports:
        return enabled_ports, {str(k): v for k, v in connector_modes.items()}

    if connector_modes:
        return [], {str(k): v for k, v in connector_modes.items()}

    enabled_ports = list(range(1, ir_ports + 1))
    fallback_modes = {str(connector): "UNKNOWN" for connector in enabled_ports}
    return enabled_ports, fallback_modes


async def async_get_ir_capability(client: ItachClient) -> ItachIrCapability:
    """Query the iTach for its current infrared connector capability."""
    ir_module, ir_ports = await client.async_get_ir_module()
    connector_modes = await client.async_get_ir_connector_modes(ir_module, ir_ports)
    enabled_ports, connector_modes_for_storage = enabled_ir_ports_with_fallback(
        connector_modes,
        ir_ports,
    )

    return ItachIrCapability(
        module=ir_module,
        ports=ir_ports,
        enabled_ports=enabled_ports,
        connector_modes=connector_modes_for_storage,
    )
