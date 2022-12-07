"""Constants for the Whirlpool Appliances integration."""

from whirlpool.backendselector import Region
from whirlpool.washerdryer import MachineState, WasherDryer

DOMAIN = "whirlpool"
CONF_ALLOWED_REGIONS = ["EU", "US"]

CONF_REGIONS_MAP = {
    "EU": Region.EU,
    "US": Region.US,
}

TANK_FILL = {
    "0": "Unknown",
    "1": "Empty",
    "2": "25%",
    "3": "50%",
    "4": "100%",
}

MACHINE_STATE = {
    MachineState.Standby: "Standby",
    MachineState.Setting: "Setting",
    MachineState.DelayCountdownMode: "Delay Countdown",
    MachineState.DelayPause: "Delay Paused",
    MachineState.SmartDelay: "Smart Delay",
    MachineState.SmartGridPause: "Smart Grid Pause",
    MachineState.Pause: "Pause",
    MachineState.RunningMainCycle: "Running Maincycle",
    MachineState.RunningPostCycle: "Running Postcycle",
    MachineState.Exceptions: "Exception",
    MachineState.Complete: "Complete",
    MachineState.PowerFailure: "Power Failure",
    MachineState.ServiceDiagnostic: "Service Diagnostic Mode",
    MachineState.FactoryDiagnostic: "Factory Diagnostic Mode",
    MachineState.LifeTest: "Life Test",
    MachineState.CustomerFocusMode: "Customer Focus Mode",
    MachineState.DemoMode: "Demo Mode",
    MachineState.HardStopOrError: "Hard Stop or Error",
    MachineState.SystemInit: "System Initialize",
}

WASHER_STATE = {
    0: "Cycle Filling",
    1: "Cycle Rinsing",
    2: "Cycle Sensing",
    3: "Cycle Soaking",
    4: "Cycle Spinning",
    5: "Cycle Washing",
}

CYCLE_FUNC = [
    WasherDryer.get_cycle_status_filling,
    WasherDryer.get_cycle_status_rinsing,
    WasherDryer.get_cycle_status_sensing,
    WasherDryer.get_cycle_status_soaking,
    WasherDryer.get_cycle_status_spinning,
    WasherDryer.get_cycle_status_washing,
]

ICON_D = "mdi:tumble-dryer"
ICON_W = "mdi:washing-machine"
