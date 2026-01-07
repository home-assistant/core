#!/usr/bin/env python3
"""CLI tool to probe Modbus values."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import struct
from typing import Any

try:
    # pymodbus 3.x async client
    from pymodbus.client import AsyncModbusTcpClient
except ImportError:  # pragma: no cover - fallback is unlikely used on HA
    AsyncModbusTcpClient: type[AsyncModbusTcpClient] | None = None  # type: ignore[no-redef]


def _decode_registers(
    regs: list[int], data_type: str, byteorder: str, wordorder: str
) -> Any:
    # Normalize to two registers when needed
    if data_type in {"float32", "uint32", "int32"}:
        if len(regs) < 2:
            raise ValueError("Need 2 registers for 32-bit type")
        hi, lo = regs[0] & 0xFFFF, regs[1] & 0xFFFF
        if wordorder.lower().startswith("little"):
            hi, lo = lo, hi
        raw = struct.pack(
            ">HH" if byteorder.lower().startswith("big") else "<HH",
            hi,
            lo,
        )
        if data_type == "float32":
            return struct.unpack(
                ">f" if byteorder.lower().startswith("big") else "<f", raw
            )[0]
        if data_type == "uint32":
            return struct.unpack(
                ">I" if byteorder.lower().startswith("big") else "<I", raw
            )[0]
        return struct.unpack(
            ">i" if byteorder.lower().startswith("big") else "<i", raw
        )[0]

    v = regs[0] & 0xFFFF
    if data_type == "int16":
        return v - 0x10000 if v & 0x8000 else v
    if data_type == "uint16":
        return v
    # default: raw 16-bit value
    return v


async def _read_async(
    host: str,
    port: int,
    slave: int,
    address: int,
    kind: str,
    data_type: str,
    byteorder: str,
    wordorder: str,
) -> None:
    if AsyncModbusTcpClient is None:
        raise RuntimeError("AsyncModbusTcpClient unavailable. Is pymodbus installed?")

    client = AsyncModbusTcpClient(host, port=port)
    try:
        ok = await client.connect()
        if ok is False:
            raise RuntimeError("Failed to connect")

        async def _call(method: Any, **kwargs: Any) -> Any:
            # Try with slave first, then unit, finally without either
            try:
                return await method(**{**kwargs, "slave": slave})
            except TypeError:
                try:
                    return await method(**{**kwargs, "unit": slave})
                except TypeError:
                    # as a last resort, call without unit/slave
                    return await method(**kwargs)

        if kind == "discrete":
            rr = await _call(client.read_discrete_inputs, address=address, count=1)
            print("Raw bits:", getattr(rr, "bits", None))  # noqa: T201
            return

        if kind == "coil":
            rr = await _call(client.read_coils, address=address, count=1)
            print("Raw bits:", getattr(rr, "bits", None))  # noqa: T201
            return

        count = 2 if data_type in {"float32", "uint32", "int32"} else 1
        if kind == "input":
            rr = await _call(client.read_input_registers, address=address, count=count)
        else:
            rr = await _call(
                client.read_holding_registers, address=address, count=count
            )
        regs = getattr(rr, "registers", None)
        print("Raw regs:", regs)  # noqa: T201
        if regs:
            print(  # noqa: T201
                "Decoded:",
                _decode_registers(
                    regs, data_type, byteorder=byteorder, wordorder=wordorder
                ),
            )
    finally:
        with contextlib.suppress(Exception):
            client.close()


def main() -> None:
    """Probe modbus."""
    p = argparse.ArgumentParser(description="Probe a Modbus/TCP value using pymodbus")
    p.add_argument("--host", required=True, help="Heat pump IP or hostname")
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--unit", type=int, default=1, help="Modbus unit/slave id")
    p.add_argument("--address", type=int, required=True, help="Register/coil address")
    p.add_argument(
        "--kind",
        choices=["input", "holding", "coil", "discrete"],
        default="input",
        help="Which table to read from",
    )
    p.add_argument(
        "--data-type",
        choices=["uint16", "int16", "uint32", "int32", "float32"],
        default="uint16",
    )
    p.add_argument(
        "--byte-order",
        choices=["big", "little"],
        default="big",
        help="Byte order inside each 16-bit word",
    )
    p.add_argument(
        "--word-order",
        choices=["big", "little"],
        default="big",
        help="Word order for 32-bit values",
    )
    args = p.parse_args()

    asyncio.run(
        _read_async(
            host=args.host,
            port=args.port,
            slave=args.unit,
            address=args.address,
            kind=args.kind,
            data_type=args.data_type,
            byteorder=args.byte_order,
            wordorder=args.word_order,
        )
    )


if __name__ == "__main__":
    main()
