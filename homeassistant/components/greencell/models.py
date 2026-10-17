"""Type definitions for Greencell integration."""

from dataclasses import dataclass

from greencell_client.access import GreencellAccess
from greencell_client.elec_data import ElecData3Phase, ElecDataSinglePhase

from homeassistant.config_entries import ConfigEntry


@dataclass
class GreencellRuntimeData:
    """Runtime data for Greencell integration."""

    access: GreencellAccess
    current_data: ElecData3Phase
    voltage_data: ElecData3Phase
    power_data: ElecDataSinglePhase
    state_data: ElecDataSinglePhase


type GreencellConfigEntry = ConfigEntry[GreencellRuntimeData]
