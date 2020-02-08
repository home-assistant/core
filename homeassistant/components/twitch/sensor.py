"""Support for Twitch sensors."""
import logging
from typing import Callable, List, Union

from twitch import Helix
from twitch.helix import StreamNotFound, User

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import TwitchEntity
from .const import (
    DATA_BOX_ART_URL,
    DATA_CHANNEL_VIEWS,
    DATA_GAME,
    DATA_LIVE,
    DATA_THUMBNAIL_URL,
    DATA_TWITCH_CLIENT,
    DATA_USER,
    DATA_VIEWERS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Twitch sensor based on a config entry."""
    twitch: Helix = hass.data[DOMAIN][entry.entry_id][DATA_TWITCH_CLIENT]

    user = twitch.user(entry.data[DATA_USER])

    sensors = [
        TwitchUserLiveSensor(entry.entry_id, user, twitch),
        TwitchUserViewersSensor(entry.entry_id, user, twitch),
        TwitchUserGameSensor(entry.entry_id, user, twitch),
    ]

    async_add_entities(sensors, True)


class TwitchSensor(TwitchEntity):
    """Defines a Twitch sensor."""

    def __init__(
        self,
        entry_id: str,
        twitch: Helix,
        user: User,
        name: str,
        icon: str,
        key: str,
        unit_of_measurement: str = "",
        enabled_default: bool = True,
    ) -> None:
        """Initialize Twitch sensor."""
        self._state = None
        self._entity_picture = None
        self._unit_of_measurement = unit_of_measurement
        self._key = key

        super().__init__(entry_id, twitch, user, name, icon, enabled_default)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.id}_{self._key}"

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def entity_picture(self):
        """Return preview of current game."""
        return self._entity_picture


class TwitchUserLiveSensor(TwitchSensor):
    """Defines a Twitch User Live sensor."""

    def __init__(self, entry_id: str, user: User, twitch: Helix) -> None:
        """Initialize Twitch User Live sensor."""
        self.user = user
        self.id = self.user.id
        self._entity_picture = self.user.profile_image_url
        super().__init__(
            entry_id,
            twitch,
            user,
            f"{self.user.display_name} Live",
            "mdi:twitch",
            DATA_LIVE,
            enabled_default=True,
        )

    async def _twitch_update(self) -> None:
        """Update Twitch User Live sensor."""
        try:
            stream = self.twitch.stream(user_id=self.user.id)
            self._state = stream.title
            thumbnail_url = stream.thumbnail_url.format(width="0", height="0")
            self._attributes = {
                DATA_CHANNEL_VIEWS: self.user.view_count,
                DATA_THUMBNAIL_URL: thumbnail_url,
            }
            self._entity_picture = thumbnail_url
        except StreamNotFound:
            self._state = "Offline"
            self._entity_picture = self.user.profile_image_url


class TwitchUserViewersSensor(TwitchSensor):
    """Defines a Twitch User Viewers sensor."""

    def __init__(self, entry_id: str, user: User, twitch: Helix) -> None:
        """Initialize Twitch User Viewers sensor."""
        self.user = user
        self.id = self.user.id
        self._entity_picture = self.user.profile_image_url
        super().__init__(
            entry_id,
            twitch,
            user,
            f"{self.user.display_name} Viewers",
            "mdi:twitch",
            DATA_VIEWERS,
            enabled_default=True,
        )

    async def _twitch_update(self) -> None:
        """Update Twitch User Viewers sensor."""
        try:
            stream = self.twitch.stream(user_id=self.user.id)
            self._state = stream.viewer_count
            thumbnail_url = stream.thumbnail_url.format(width="0", height="0")
            self._entity_picture = thumbnail_url
        except StreamNotFound:
            self._state = 0
            self._entity_picture = self.user.profile_image_url


class TwitchUserGameSensor(TwitchSensor):
    """Defines a Twitch User Game sensor."""

    def __init__(self, entry_id: str, user: User, twitch: Helix) -> None:
        """Initialize Twitch User Game sensor."""
        self.user = user
        self.id = self.user.id
        self._entity_picture = self.user.profile_image_url
        super().__init__(
            entry_id,
            twitch,
            user,
            f"{self.user.display_name} Current Game",
            "mdi:twitch",
            DATA_GAME,
            enabled_default=True,
        )

    async def _twitch_update(self) -> None:
        """Update Twitch User Game sensor."""
        try:
            stream = self.twitch.stream(user_id=self.user.id)
            game = self.twitch.game(id=stream.game_id)
            if game is None:
                self._state = "Unknown"
                self._entity_picture = self.user.profile_image_url
            else:
                self._state = game.name
                box_art_url = game.box_art_url.format(width="0", height="0")
                self._attributes = {DATA_BOX_ART_URL: box_art_url}
                self._entity_picture = box_art_url
        except StreamNotFound:
            self._state = "Unknown"
            self._entity_picture = self.user.profile_image_url
