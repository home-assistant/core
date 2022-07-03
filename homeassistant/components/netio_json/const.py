"""Constants for the NetIO JSON integration."""
from datetime import timedelta

DOMAIN = "netio_json"

DATA_NETIO_CLIENT = "netio_client"

SCAN_INTERVAL = timedelta(seconds=10)

API_GLOBAL_MEASURE = "GlobalMeasure"
API_OUTLET = "Outputs"
API_GLOBAL_VOLTAGE = "Voltage"
API_GLOBAL_FREQUENCY = "Frequency"
API_GLOBAL_CURRENT = "TotalCurrent"
API_GLOBAL_POWERFACTOR = "TotalPowerFactor"
API_GLOBAL_PHASE = "TotalPhase"
API_GLOBAL_LOAD = "TotalLoad"
API_GLOBAL_ENERGY = "TotalEnergy"
API_GLOBAL_REVERSE_ENERGY = "TotalReverseEnergy"
API_GLOBAL_ENERGY_START = "EnergyStart"
API_OUTLET_CURRENT = "Current"
API_OUTLET_POWERFACTOR = "PowerFactor"
API_OUTLET_PHASE = "Phase"
API_OUTLET_ENERGY = "Energy"
API_OUTLET_LOAD = "Load"
API_OUTLET_REVERSE_ENERGY = "ReverseEnergy"
API_OUTLET_STATE = "State"
