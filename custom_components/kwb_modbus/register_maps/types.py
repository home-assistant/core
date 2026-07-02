"""Shared register definition types used by all register map versions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RegisterDef:
    """Definition of a single Modbus register."""

    address: int
    count: int
    name: str
    param: str
    data_type: str  # s16, u16, s32, u32
    unit: str
    scale: float
    index: str  # e.g. "BUF 1", "HC 1.1", "" if none
    value_table: str  # name of value table or ""
    is_status: bool  # True if this is a sensor_status register
    writable: bool = True


@dataclass
class SelectRegisterDef:
    """Writable program/mode register (Holding Register, func 03 read / 06 write)."""

    address: int
    name: str
    param: str
    index: str
    value_table: str
    data_type: str
    module: str
