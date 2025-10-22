"""Nintendo parental controls data coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from pynintendoparental import Authenticator, NintendoParental
from pynintendoparental.exceptions import (
    InvalidOAuthConfigurationException,
    NoDevicesFoundException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

type NintendoParentalControlsConfigEntry = ConfigEntry[NintendoUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(seconds=60)


class NintendoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Nintendo data update coordinator."""

    config_entry: NintendoParentalControlsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        authenticator: Authenticator,
        config_entry: NintendoParentalControlsConfigEntry,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.api = NintendoParental(
            authenticator, hass.config.time_zone, hass.config.language
        )

    async def _async_update_data(self) -> None:
        """Update data from Nintendo's API."""
        try:
            return await self.api.update()
        except InvalidOAuthConfigurationException as err:
            raise ConfigEntryError(
                err, translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except NoDevicesFoundException as err:
            ir.async_create_issue(
                hass=self.hass,
                domain=DOMAIN,
                issue_id="no_devices_found",
                is_persistent=False,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="no_devices_found",
                translation_placeholders={
                    "account_id": self.config_entry.title,
                    "placeholder": "Nintendo Switch Parental Controls",
                },
            )
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="no_devices_found",
            ) from err
