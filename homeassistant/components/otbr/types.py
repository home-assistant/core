"""The Open Thread Border Router integration types."""

from homeassistant.config_entries import ConfigEntry

from .util import OTBRData

type OTBRConfigEntry = ConfigEntry[OTBRData]
