"""Support for the Twitch stream status."""
from __future__ import annotations

import functools as ft

from twitchAPI.twitch import (
    AuthScope,
    InvalidTokenException,
    MissingScopeException,
    Twitch,
    TwitchAuthorizationException,
)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_FOLLOWERS,
    ATTR_FOLLOWING,
    ATTR_FOLLOWING_SINCE,
    ATTR_GAME,
    ATTR_SUBSCRIBED,
    ATTR_SUBSCRIPTION_GIFTED,
    ATTR_TITLE,
    ATTR_VIEWS,
    CONF_CHANNELS,
    LOGGER,
    STATE_OFFLINE,
    STATE_STREAMING,
)
from .coordinator import TwitchDataUpdateCoordinator

OAUTH_SCOPES = [AuthScope.USER_READ_SUBSCRIPTIONS]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Required(CONF_CHANNELS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_TOKEN): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Twitch platform."""
    channels = config[CONF_CHANNELS]
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    oauth_token = config.get(CONF_TOKEN)

    try:
        client = await hass.async_add_executor_job(
            ft.partial(
                Twitch,
                app_id=client_id,
                app_secret=client_secret,
                target_app_auth_scope=OAUTH_SCOPES,
            )
        )
        client.auto_refresh_auth = False
    except TwitchAuthorizationException:
        LOGGER.error("Invalid client ID or client secret")
        return

    if oauth_token:
        try:
            await hass.async_add_executor_job(
                ft.partial(
                    client.set_user_authentication,
                    token=oauth_token,
                    scope=OAUTH_SCOPES,
                    validate=True,
                )
            )
        except MissingScopeException:
            LOGGER.error("OAuth token is missing required scope")
            return
        except InvalidTokenException:
            LOGGER.error("OAuth token is invalid")
            return

    user = None
    if config.get(CONF_TOKEN):
        user = (await hass.async_add_executor_job(client.get_users))["data"][0]["id"]
    channels = await hass.async_add_executor_job(
        ft.partial(client.get_users, logins=channels)
    )
    coordinator = TwitchDataUpdateCoordinator(hass, client, user, channels["data"])
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            TwitchSensor(
                coordinator,
                channel,
            )
            for channel in channels["data"]
        ],
    )


class TwitchSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Twitch channel."""

    _attr_icon = "mdi:twitch"
    coordinator: TwitchDataUpdateCoordinator

    def __init__(
        self, coordinator: TwitchDataUpdateCoordinator, channel: dict[str, str]
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = channel["display_name"]
        self._attr_unique_id = channel["id"]

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.unique_id in self.coordinator.streams:
            return STATE_STREAMING
        return STATE_OFFLINE

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture of the sensor."""
        if self.unique_id in self.coordinator.streams:
            return self.coordinator.streams[self.unique_id]["thumbnail_url"]
        if self.unique_id in self.coordinator.users:
            return self.coordinator.users[self.unique_id]["offline_image_url"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return attributes for the sensor."""
        attrs: dict[str, StateType] = {}
        if self.unique_id in self.coordinator.followers:
            attrs[ATTR_FOLLOWERS] = self.coordinator.followers[self.unique_id]
        if self.unique_id in self.coordinator.users:
            attrs[ATTR_VIEWS] = self.coordinator.users[self.unique_id]["view_count"]
        attrs[ATTR_FOLLOWING] = False
        if self.unique_id in self.coordinator.follows and self.coordinator.user:
            attrs[ATTR_FOLLOWING] = True
            attrs[ATTR_FOLLOWING_SINCE] = self.coordinator.follows[self.unique_id][
                "followed_at"
            ]
        if self.unique_id in self.coordinator.subs:
            attrs[ATTR_SUBSCRIBED] = "data" in self.coordinator.subs[self.unique_id]
            if "data" in self.coordinator.subs[self.unique_id]:
                attrs[ATTR_SUBSCRIPTION_GIFTED] = self.coordinator.subs[self.unique_id][
                    "data"
                ][0]["is_gift"]
            LOGGER.debug(self.coordinator.subs[self.unique_id])
        if self.unique_id in self.coordinator.streams:
            attrs[ATTR_GAME] = self.coordinator.streams[self.unique_id]["game_name"]
            attrs[ATTR_TITLE] = self.coordinator.streams[self.unique_id]["title"]
        else:
            attrs[ATTR_GAME] = None
            attrs[ATTR_TITLE] = None
        return attrs
