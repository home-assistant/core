"""Data models for the Orvibo integration."""

from orvibo.s20 import S20

from homeassistant.config_entries import ConfigEntry

type S20ConfigEntry = ConfigEntry[S20]
