"""Helpers to deal with Cast devices."""
from typing import Optional, Tuple

import attr
from pychromecast.const import CAST_MANUFACTURERS

from .const import DEFAULT_PORT


@attr.s(slots=True, frozen=True)
class ChromecastInfo:
    """Class to hold all data about a chromecast for creating connections.

    This also has the same attributes as the mDNS fields by zeroconf.
    """

    services: Optional[set] = attr.ib()
    host: Optional[str] = attr.ib(default=None)
    port: Optional[int] = attr.ib(default=0)
    uuid: Optional[str] = attr.ib(
        converter=attr.converters.optional(str), default=None
    )  # always convert UUID to string if not None
    model_name: str = attr.ib(default="")
    friendly_name: Optional[str] = attr.ib(default=None)

    @property
    def is_audio_group(self) -> bool:
        """Return if this is an audio group."""
        return self.port != DEFAULT_PORT

    @property
    def host_port(self) -> Tuple[str, int]:
        """Return the host+port tuple."""
        return self.host, self.port

    @property
    def manufacturer(self) -> str:
        """Return the manufacturer."""
        if not self.model_name:
            return None
        return CAST_MANUFACTURERS.get(self.model_name.lower(), "Google Inc.")


class ChromeCastZeroconf:
    """Class to hold a zeroconf instance."""

    __zconf = None

    @classmethod
    def set_zeroconf(cls, zconf):
        """Set zeroconf."""
        cls.__zconf = zconf

    @classmethod
    def get_zeroconf(cls):
        """Get zeroconf."""
        return cls.__zconf


class CastStatusListener:
    """Helper class to handle pychromecast status callbacks.

    Necessary because a CastDevice entity can create a new socket client
    and therefore callbacks from multiple chromecast connections can
    potentially arrive. This class allows invalidating past chromecast objects.
    """

    def __init__(self, cast_device, chromecast, mz_mgr):
        """Initialize the status listener."""
        self._cast_device = cast_device
        self._uuid = chromecast.uuid
        self._valid = True
        self._mz_mgr = mz_mgr

        chromecast.register_status_listener(self)
        chromecast.socket_client.media_controller.register_status_listener(self)
        chromecast.register_connection_listener(self)
        if cast_device._cast_info.is_audio_group:
            self._mz_mgr.add_multizone(chromecast)
        else:
            self._mz_mgr.register_listener(chromecast.uuid, self)

    def new_cast_status(self, cast_status):
        """Handle reception of a new CastStatus."""
        if self._valid:
            self._cast_device.new_cast_status(cast_status)

    def new_media_status(self, media_status):
        """Handle reception of a new MediaStatus."""
        if self._valid:
            self._cast_device.new_media_status(media_status)

    def new_connection_status(self, connection_status):
        """Handle reception of a new ConnectionStatus."""
        if self._valid:
            self._cast_device.new_connection_status(connection_status)

    @staticmethod
    def added_to_multizone(group_uuid):
        """Handle the cast added to a group."""

    def removed_from_multizone(self, group_uuid):
        """Handle the cast removed from a group."""
        if self._valid:
            self._cast_device.multizone_new_media_status(group_uuid, None)

    def multizone_new_cast_status(self, group_uuid, cast_status):
        """Handle reception of a new CastStatus for a group."""

    def multizone_new_media_status(self, group_uuid, media_status):
        """Handle reception of a new MediaStatus for a group."""
        if self._valid:
            self._cast_device.multizone_new_media_status(group_uuid, media_status)

    def invalidate(self):
        """Invalidate this status listener.

        All following callbacks won't be forwarded.
        """
        # pylint: disable=protected-access
        if self._cast_device._cast_info.is_audio_group:
            self._mz_mgr.remove_multizone(self._uuid)
        else:
            self._mz_mgr.deregister_listener(self._uuid, self)
        self._valid = False
