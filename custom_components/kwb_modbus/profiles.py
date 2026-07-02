"""Register profile resolution for different KWB firmware families."""

from __future__ import annotations

from dataclasses import dataclass

from .const import (
    DEFAULT_REGISTER_PROFILE,
    REGISTER_PROFILE_AUTO,
    REGISTER_PROFILE_V22,
    REGISTER_PROFILE_V25,
)
from .register_maps.types import RegisterDef, SelectRegisterDef
from .register_maps.v22_4_0 import REGISTERS, SELECT_REGISTERS, VALUE_TABLES
from .register_maps.v25_4_1 import (
    REGISTERS as REGISTERS_V25,
    SELECT_REGISTERS as SELECT_REGISTERS_V25,
    VALUE_TABLES as VALUE_TABLES_V25,
)


@dataclass(frozen=True)
class RegisterProfile:
    """Container for one firmware-specific register profile."""

    key: str
    registers: dict[str, list[RegisterDef]]
    select_registers: dict[str, list[SelectRegisterDef]]
    value_tables: dict[str, dict[int, str]]


REGISTER_PROFILES: dict[str, RegisterProfile] = {
    REGISTER_PROFILE_V22: RegisterProfile(
        key=REGISTER_PROFILE_V22,
        registers=REGISTERS,
        select_registers=SELECT_REGISTERS,
        value_tables=VALUE_TABLES,
    ),
    REGISTER_PROFILE_V25: RegisterProfile(
        key=REGISTER_PROFILE_V25,
        registers=REGISTERS_V25,
        select_registers=SELECT_REGISTERS_V25,
        value_tables=VALUE_TABLES_V25,
    ),
}


def detect_profile_key_from_firmware(major: int | None) -> str | None:
    """Return best matching profile key for detected firmware major version."""
    if major is None:
        return None
    if major == 22:
        return REGISTER_PROFILE_V22
    if major >= 25:
        return REGISTER_PROFILE_V25
    return None


def resolve_profile_key(selected_key: str, detected_key: str | None) -> str:
    """Resolve selected profile (or auto) to an available concrete profile key."""
    candidate = detected_key if selected_key == REGISTER_PROFILE_AUTO else selected_key
    if candidate in REGISTER_PROFILES:
        return candidate
    return DEFAULT_REGISTER_PROFILE


def get_register_profile(
    selected_key: str, detected_key: str | None = None
) -> RegisterProfile:
    """Return resolved register profile object."""
    return REGISTER_PROFILES[resolve_profile_key(selected_key, detected_key)]
