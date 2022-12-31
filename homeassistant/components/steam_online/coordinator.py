"""Data update coordinator for the Steam integration."""
from __future__ import annotations

from datetime import timedelta

from steam.api import HTTPError, HTTPTimeoutError, interface, key
from steam.user import profile, profile_batch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ACCOUNTS, DOMAIN, LOGGER


class SteamDataUpdateCoordinator(DataUpdateCoordinator[dict[int, profile]]):
    """Data update coordinator for the Steam integration."""

    config_entry: ConfigEntry
    data: dict[int, profile]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.game_icons: dict[int, str] = {}
        key.set(self.config_entry.data[CONF_API_KEY])

    def _update(self) -> dict[int, profile]:
        """Fetch data from API endpoint."""
        _ids = list(self.config_entry.options[CONF_ACCOUNTS])
        reg = er.async_get(self.hass)
        if not self.game_icons:
            _interface = interface("IPlayerService")
            for _id in _ids:
                # Some users might have their games hidden
                if games := _interface.GetOwnedGames(steamid=_id, include_appinfo=1)[
                    "response"
                ].get("games"):
                    self.game_icons = self.game_icons | {
                        game["appid"]: game["img_icon_url"] for game in games
                    }

        profiles = {}
        _profile: profile
        for _profile in profile_batch(_ids):
            entity_id = f"sensor.{_profile.persona}_level".replace(" ", "_").lower()
            if (entry := reg.async_get(entity_id)) and not entry.disabled:
                # Property is blocking. So we call it here
                # Has it's own separate api call. Saving IO as level is off by default
                _profile.level  # pylint:disable=pointless-statement
            profiles[_profile.id64] = _profile
        return profiles

    async def _async_update_data(self) -> dict[int, profile]:
        """Send request to the executor."""
        try:
            return await self.hass.async_add_executor_job(self._update)

        except (HTTPError, HTTPTimeoutError) as ex:
            if "401" in str(ex):
                raise ConfigEntryAuthFailed from ex
            raise UpdateFailed(ex) from ex
