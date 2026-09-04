"""Shared data models for the Powersensor integration."""

from dataclasses import dataclass

from powersensor_local import VirtualHousehold
from powersensor_local.zeroconf_devices import PowersensorZeroconfDevices

from homeassistant.config_entries import ConfigEntry

from .powersensor_message_dispatcher import PowersensorMessageDispatcher


@dataclass
class PowersensorVirtualHouseholdState:
    """Tracks which Virtual Household entity groups have been added to HA.

    Owned by sensor.py's async_setup_entry closure and reset on every reload
    so that a fresh load always starts clean.  Held in models.py so it can be
    imported and constructed directly in tests without going through setup.
    """

    mains_added: bool = False
    solar_added: bool = False


@dataclass
class PowersensorRuntimeData:
    """Typed container for data stored on a Powersensor config entry.

    All fields are set by __init__.py's async_setup_entry and remain
    stable for the lifetime of the entry.  Sensor-platform bookkeeping
    (VHH flags, role-entity tracking) lives as local state inside
    sensor.py's async_setup_entry closure, where it is owned and reset
    on every load without touching this dataclass.
    """

    vhh: VirtualHousehold
    dispatcher: PowersensorMessageDispatcher
    devices: PowersensorZeroconfDevices


type PowersensorConfigEntry = ConfigEntry[PowersensorRuntimeData]
