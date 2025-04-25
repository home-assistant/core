"""Type defs for ntfy integration."""

from aiontfy import Ntfy

from homeassistant.config_entries import ConfigEntry

type NtfyConfigEntry = ConfigEntry[Ntfy]
