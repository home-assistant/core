"""State."""

from datetime import datetime


class ControllableLoadPlanState:
    """Represents the planned state of a controllable load."""

    def __init__(self) -> None:
        """Initialize the controllable load plan state."""
        self.is_on: bool = False
        self.expected_load_amps: int = 0
        self.throttle_amps: float = 0.0


class PlanState:
    """Represents the overall planned state for load control."""

    def __init__(self) -> None:
        """Initialize the plan state."""
        self.available_amps: float = 0
        self.used_amps: float = 0
        self.controllable_loads: dict[str, ControllableLoadPlanState] = {}


class ControllableLoadState:
    """Represents the current state of a controllable load."""

    def __init__(self) -> None:
        """Initialize the controllable load state."""
        self.is_on: bool = False  # Actual state of the switch
        self.is_on_load_control: bool = False  # True if we have turned it on
        self.last_toggled: datetime | None = None
        self.last_throttled: datetime | None = None
        self.current_load_amps: float = 0.0


class State:
    """Represents the current state the overall integration."""

    def __init__(self) -> None:
        """Initialize the state."""
        self.available_amps: float = 0
        self.house_consumption_amps: float = 0.0
        self.load_control_consumption_amps: float = 0.0
        self.mains_voltage: float = 230.0
        self.allow_grid_import: bool = True
        self.solar_generation_kw: float = 0.0
        self.controllable_loads: dict[str, ControllableLoadState] = {}
