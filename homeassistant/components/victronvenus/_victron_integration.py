from victronvenusclient import Hub as VictronHub

from homeassistant.config_entries import ConfigEntry

type VictronVenusConfigEntry = ConfigEntry[VictronHub]
