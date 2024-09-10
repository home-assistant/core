"""Support for Oncue types."""

from __future__ import annotations

from aiooncue import OncueDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

type OncueConfigEntry = ConfigEntry[DataUpdateCoordinator[dict[str, OncueDevice]]]
