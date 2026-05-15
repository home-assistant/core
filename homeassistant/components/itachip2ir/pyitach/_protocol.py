"""iTach protocol helpers.

This module must not perform any I/O.
"""

from typing import Any

from ._exceptions import ItachResponseError


def build_sendir_command(
    *,
    module: int,
    connector: int,
    command_id: int,
    carrier_frequency: int,
    repeat: int,
    offset: int,
    timings: list[int],
) -> str:
    """Build a Global Caché sendir command."""
    timings_str = ",".join(str(value) for value in timings)

    return (
        f"sendir,{module}:{connector},{command_id},{carrier_frequency},"
        f"{repeat},{offset},{timings_str}\r"
    )


def build_completeir_response_prefix(
    *,
    module: int,
    connector: int,
    command_id: int,
) -> str:
    """Build expected completeir response prefix."""
    return f"completeir,{module}:{connector},{command_id}"


def parse_ir_response(response: str) -> tuple[int, int, str] | None:
    """Parse a get_IR response."""
    parts = [part.strip() for part in response.split(",")]
    if len(parts) < 3 or parts[0] != "IR":
        return None

    address = parts[1].split(":")
    if len(address) != 2:
        return None

    try:
        module = int(address[0])
        connector = int(address[1])
    except ValueError:
        return None

    mode = parts[2].upper()
    if not mode:
        return None

    return module, connector, mode


def parse_device_line(line: str) -> dict[str, int | str] | None:
    """Parse one getdevices response line."""
    parts = line.strip().split()
    if len(parts) < 2:
        return None

    values = parts[0].split(",")
    if len(values) != 3 or values[0].lower() != "device":
        return None

    try:
        module = int(values[1])
        ports = int(values[2])
    except ValueError:
        return None

    if module < 0 or ports < 0:
        return None

    return {
        "module": module,
        "ports": ports,
        "type": parts[1].strip().upper(),
    }


def parse_net_response(response: str) -> dict[str, Any]:
    """Parse a get_NET response."""
    parts = [part.strip() for part in response.split(",")]

    if len(parts) < 2 or parts[0] != "NET":
        raise ItachResponseError(f"Malformed get_NET response: {response}")

    labels = (
        "ip_address",
        "subnet_mask",
        "gateway",
        "dhcp_enabled",
        "dns_server",
        "mac_address",
    )

    info: dict[str, Any] = {
        "raw": response,
        "address": parts[1],
    }
    info.update(dict(zip(labels, parts[2:], strict=False)))

    if len(parts) > len(labels) + 2:
        info["extra_fields"] = parts[len(labels) + 2 :]

    return info
