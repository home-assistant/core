"""Constants for the Hanna integration."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import HannaDataCoordinator

DOMAIN = "hanna"


class HannaConfigEntry(ConfigEntry):
    """Config entry for Hanna integration with typed runtime data."""

    runtime_data: dict[str, "HannaDataCoordinator"] | None
