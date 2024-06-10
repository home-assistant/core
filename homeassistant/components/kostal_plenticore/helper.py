"""Code to handle the Plenticore API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pykoplenti import ApiClient, ApiException

_KNOWN_HOSTNAME_IDS = ("Network:Hostname", "Hostname")


class PlenticoreDataFormatter:
    """Provides method to format values of process or settings data."""

    INVERTER_STATES = {
        0: "Off",
        1: "Init",
        2: "IsoMEas",
        3: "GridCheck",
        4: "StartUp",
        6: "FeedIn",
        7: "Throttled",
        8: "ExtSwitchOff",
        9: "Update",
        10: "Standby",
        11: "GridSync",
        12: "GridPreCheck",
        13: "GridSwitchOff",
        14: "Overheating",
        15: "Shutdown",
        16: "ImproperDcVoltage",
        17: "ESB",
    }

    EM_STATES = {
        0: "Idle",
        1: "n/a",
        2: "Emergency Battery Charge",
        4: "n/a",
        8: "Winter Mode Step 1",
        16: "Winter Mode Step 2",
    }

    @classmethod
    def get_method(cls, name: str) -> Callable[[Any], Any]:
        """Return a callable formatter of the given name."""
        return getattr(cls, name)

    @staticmethod
    def format_round(state: str) -> int | str:
        """Return the given state value as rounded integer."""
        try:
            return round(float(state))
        except (TypeError, ValueError):
            return state

    @staticmethod
    def format_round_back(value: float) -> str:
        """Return a rounded integer value from a float."""
        try:
            if isinstance(value, float) and value.is_integer():
                int_value = int(value)
            elif isinstance(value, int):
                int_value = value
            else:
                int_value = round(value)

            return str(int_value)
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def format_float(state: str) -> float | str:
        """Return the given state value as float rounded to three decimal places."""
        try:
            return round(float(state), 3)
        except (TypeError, ValueError):
            return state

    @staticmethod
    def format_energy(state: str) -> float | str:
        """Return the given state value as energy value, scaled to kWh."""
        try:
            return round(float(state) / 1000, 1)
        except (TypeError, ValueError):
            return state

    @staticmethod
    def format_inverter_state(state: str) -> str | None:
        """Return a readable string of the inverter state."""
        try:
            value = int(state)
        except (TypeError, ValueError):
            return state

        return PlenticoreDataFormatter.INVERTER_STATES.get(value)

    @staticmethod
    def format_em_manager_state(state: str) -> str | None:
        """Return a readable state of the energy manager."""
        try:
            value = int(state)
        except (TypeError, ValueError):
            return state

        return PlenticoreDataFormatter.EM_STATES.get(value)


async def get_hostname_id(client: ApiClient) -> str:
    """Check for known existing hostname ids."""
    all_settings = await client.get_settings()
    for entry in all_settings["scb:network"]:
        if entry.id in _KNOWN_HOSTNAME_IDS:
            return entry.id
    raise ApiException("Hostname identifier not found in KNOWN_HOSTNAME_IDS")
