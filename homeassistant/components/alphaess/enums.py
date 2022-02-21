"""Parent class for AlphaESSNames enum."""
from enum import Enum, unique


@unique
class AlphaESSNames(str, Enum):
    """Device names used by AlphaESS."""

    SolarProduction = "Solar Production"
    SolarToBattery = "Solar to Battery"
    SolarToGrid = "Solar to Grid"
    SolarToLoad = "Solar to Load"
    TotalLoad = "Total Load"
    GridToLoad = "Grid to Load"
    GridToBattery = "Grid to Battery"
    StateOfCharge = "State of Charge"
    Charge = "Charge"
    Discharge = "Discharge"
