"""State."""

from datetime import datetime


class ControllableLoadPlanState:
    is_on: bool = False
    expected_load_amps: int = 0


class PlanState:
    available_amps: float = 0
    used_amps: float = 0
    controllable_loads: dict[str, ControllableLoadPlanState] = {}


class ControllableLoadState:
    """Represents the current state of a controllable load."""

    is_on: bool = False  # Actual state of the switch
    is_on_load_control: bool = False  # True if we have turned it on
    last_toggled: datetime | None = None
    last_throttled: datetime | None = None
    current_load_amps: float = 0.0


class State:
    """Represents the current state the overall integration."""

    available_amps: float = 0
    house_consumption_amps: float = 0.0
    load_control_consumption_amps: float = 0.0
    mains_voltage: float = 230.0
    allow_grid_import: bool = True
    solar_generation_kw: float = 0.0
    controllable_loads: dict[str, ControllableLoadState] = {}
