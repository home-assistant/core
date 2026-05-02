"""Types for the Trane Local integration."""

from steamloop import ThermostatConnection

from homeassistant.config_entries import ConfigEntry

type TraneConfigEntry = ConfigEntry[ThermostatConnection]
