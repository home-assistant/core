"""API for Ondilo ICO bound to Home Assistant OAuth."""

from asyncio import run_coroutine_threadsafe
import logging
from typing import Any

from ondilo import Ondilo, OndiloError

from homeassistant import config_entries, core
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


class OndiloClient(Ondilo):
    """Provide Ondilo ICO authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ) -> None:
        """Initialize Ondilo ICO Auth."""
        self.hass = hass
        self.config_entry = config_entry
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        super().__init__(self.session.token)

    def refresh_tokens(self) -> dict:
        """Refresh and return new Ondilo ICO tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token

    def get_all_pools_data(self) -> list[dict[str, Any]]:
        """Fetch pools and add pool details and last measures to pool data."""

        pools = self.get_pools()
        for pool in pools:
            _LOGGER.debug(
                "Retrieving data for pool/spa: %s, id: %d", pool["name"], pool["id"]
            )

            try:
                pool["ICO"] = self.get_ICO_details(pool["id"])
                if not pool["ICO"]:
                    _LOGGER.error("The pool id %s does not have any ICO attached")
                    continue
            except OndiloError as exc:
                _LOGGER.error(
                    "Error retrieving ICO details of your pool id %d. Server error was: %s",
                    pool["id"],
                    exc,
                )
                continue

            try:
                pool["sensors"] = self.get_last_pool_measures(pool["id"])
                _LOGGER.debug(
                    "Retrieved the following sensors data: %s", pool["sensors"]
                )
            except OndiloError as exc:
                # Trying to retrieve data from an ICO that was replaced produces an error
                # So we'll remove the pool/spa from the list
                _LOGGER.error(
                    "Error retrieving last data of your ICO '%s'. Server error was: %s",
                    pool["ICO"],
                    exc,
                )
                pool["ICO"] = None

        return [pool for pool in pools if "ICO" in pool and pool["ICO"]]
