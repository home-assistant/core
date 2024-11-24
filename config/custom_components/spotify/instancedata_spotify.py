# noqa: ignore=all

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from spotifywebapipython import SpotifyClient
from spotifywebapipython.models import SpotifyConnectDevices

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_OPTION_DEVICE_DEFAULT,
    CONF_OPTION_DEVICE_LOGINID,
    CONF_OPTION_DEVICE_PASSWORD,
    CONF_OPTION_DEVICE_USERNAME,
    CONF_OPTION_SCRIPT_TURN_OFF,
    CONF_OPTION_SCRIPT_TURN_ON,
    CONF_OPTION_SOURCE_LIST_HIDE,
)


@dataclass
class InstanceDataSpotify:
    """
    Spotify instance data stored in the Home Assistant data object.

    This contains various attributes and object instances that the integration needs
    to function.  It is created in `__init__.py`, and referenced in various other
    modules.
    """

    devices: DataUpdateCoordinator[SpotifyConnectDevices]
    """
    List of Spotify Connect devices that are available.
    This property is refreshed every 5 minutes by a DataUpdateCoordinator.
    """

    media_player: MediaPlayerEntity
    """
    The media player instance used to control media playback.
    """

    options: MappingProxyType[str, Any]
    """
    Configuration entry options.
    """

    session: OAuth2Session
    """
    The OAuth2 session used to communicate with the Spotify Web API.
    """

    spotifyClient: SpotifyClient
    """
    The SpotifyClient instance used to interface with the Spotify Web API.
    """

    @property
    def OptionDeviceDefault(self) -> str | None:
        """
        The default Spotify Connect player device.
        """
        return self.options.get(CONF_OPTION_DEVICE_DEFAULT, None)

    @property
    def OptionDeviceLoginId(self) -> str | None:
        """
        The default Spotify Connect loginid to use when connecting to an inactive device.
        """
        return self.options.get(CONF_OPTION_DEVICE_LOGINID, None)

    @property
    def OptionDevicePassword(self) -> str | None:
        """
        The default Spotify Connect password to use when connecting to an inactive device.
        """
        return self.options.get(CONF_OPTION_DEVICE_PASSWORD, None)

    @property
    def OptionDeviceUsername(self) -> str | None:
        """
        The default Spotify Connect username to use when connecting to an inactive device.
        """
        return self.options.get(CONF_OPTION_DEVICE_USERNAME, None)

    @property
    def OptionScriptTurnOff(self) -> str | None:
        """
        Script entity id that will be called to power off the device that plays media content.
        """
        return self.options.get(CONF_OPTION_SCRIPT_TURN_OFF, None)

    @property
    def OptionScriptTurnOn(self) -> str | None:
        """
        Script entity id that will be called to power on the device that plays media content.
        """
        return self.options.get(CONF_OPTION_SCRIPT_TURN_ON, None)

    @property
    def OptionSourceListHide(self) -> list:
        """
        The list of devices to hide from the source list.
        """
        result: list = []

        # get option value.
        value: str = self.options.get(CONF_OPTION_SOURCE_LIST_HIDE, None)

        # build a list from the semi-colon delimited string.
        if value is not None:
            result = value.split(";")
            for idx in range(0, len(result)):
                result[idx] = result[idx].strip().lower()

        # return result.
        return result
