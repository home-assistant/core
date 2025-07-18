"""Family Safety coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyfamilysafety import Authenticator, FamilySafety

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(seconds=60)

type FamilySafetyConfigEntry = ConfigEntry[FamilySafetyCoordinator]


class FamilySafetyCoordinator(DataUpdateCoordinator[FamilySafety]):
    """Family Safety coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FamilySafetyConfigEntry,
        auth: Authenticator,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.api = FamilySafety(auth)
        self.update_method = self.api.update
