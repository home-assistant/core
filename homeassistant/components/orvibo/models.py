"""Data models for the Orvibo integration."""

from dataclasses import dataclass

from orvibo.s20 import S20

from homeassistant.config_entries import ConfigEntry


@dataclass
class S20Data:
    """S20 data class."""

    s20: S20


type S20ConfigEntry = ConfigEntry[S20Data]
