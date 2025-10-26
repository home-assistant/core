"""Util declarations and functions for Orvibo."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry


@dataclass
class S20Data:
    """S20 data class."""

    name: str
    host: str
    mac: str


type S20ConfigEntry = ConfigEntry[S20Data]
