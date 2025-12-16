"""Util declarations and functions for Orvibo."""

from dataclasses import dataclass

from orvibo.s20 import S20, S20Exception

from homeassistant.config_entries import ConfigEntry


@dataclass
class S20Data:
    """S20 data class."""

    exc: type[S20Exception]
    s20: S20


type S20ConfigEntry = ConfigEntry[S20Data]
