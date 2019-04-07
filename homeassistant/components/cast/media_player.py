"""Provide functionality to interact with Cast devices on the network."""
import asyncio
import logging
import threading
from typing import Optional, Tuple

import attr
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, MediaPlayerDevice)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MOVIE, MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW, SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET)
from homeassistant.const import (
    CONF_HOST, EVENT_HOMEASSISTANT_STOP, STATE_IDLE, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import homeassistant.util.dt as dt_util

from . import DOMAIN as CAST_DOMAIN

DEPENDENCIES = ('cast',)

_LOGGER = logging.getLogger(__name__)

CONF_IGNORE_CEC = 'ignore_cec'
CAST_SPLASH = 'https://home-assistant.io/images/cast/splash.png'

DEFAULT_PORT = 8009

SUPPORT_CAST = SUPPORT_PAUSE | SUPPORT_PLAY | SUPPORT_PLAY_MEDIA | \
               SUPPORT_STOP | SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
               SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET

# Stores a threading.Lock that is held by the internal pychromecast discovery.
INTERNAL_DISCOVERY_RUNNING_KEY = 'cast_discovery_running'
# Stores all ChromecastInfo we encountered through discovery or config as a set
# If we find a chromecast with a new host, the old one will be removed again.
KNOWN_CHROMECAST_INFO_KEY = 'cast_known_chromecasts'
# Stores UUIDs of cast devices that were added as entities. Doesn't store
# None UUIDs.
ADDED_CAST_DEVICES_KEY = 'cast_added_cast_devices'
# Stores an audio group manager.
CAST_MULTIZONE_MANAGER_KEY = 'cast_multizone_manager'

# Dispatcher signal fired with a ChromecastInfo every time we discover a new
# Chromecast or receive it through configuration
SIGNAL_CAST_DISCOVERED = 'cast_discovered'

# Dispatcher signal fired with a ChromecastInfo every time a Chromecast is
# removed
SIGNAL_CAST_REMOVED = 'cast_removed'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_IGNORE_CEC, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


@attr.s(slots=True, frozen=True)
class ChromecastInfo:
    """Class to hold all data about a chromecast for creating connections.

    This also has the same attributes as the mDNS fields by zeroconf.
    """

    host = attr.ib(type=str)
    port = attr.ib(type=int)
    service = attr.ib(type=Optional[str], default=None)
    uuid = attr.ib(type=Optional[str], converter=attr.converters.optional(str),
                   default=None)  # always convert UUID to string if not None
    manufacturer = attr.ib(type=str, default='')
    model_name = attr.ib(type=str, default='')
    friendly_name = attr.ib(type=Optional[str], default=None)
    is_dynamic_group = attr.ib(type=Optional[bool], default=None)

    @property
    def is_audio_group(self) -> bool:
        """Return if this is an audio group."""
        return self.port != DEFAULT_PORT

    @property
    def is_information_complete(self) -> bool:
        """Return if all information is filled out."""
        want_dynamic_group = self.is_audio_group
        have_dynamic_group = self.is_dynamic_group is not None
        have_all_except_dynamic_group = all(
            attr.astuple(self, filter=attr.filters.exclude(
                attr.fields(ChromecastInfo).is_dynamic_group)))
        return (have_all_except_dynamic_group and
                (not want_dynamic_group or have_dynamic_group))

    @property
    def host_port(self) -> Tuple[str, int]:
        """Return the host+port tuple."""
        return self.host, self.port


def _is_matching_dynamic_group(our_info: ChromecastInfo,
                               new_info: ChromecastInfo,) -> bool:
    return (our_info.is_audio_group and
            new_info.is_dynamic_group and
            our_info.friendly_name == new_info.friendly_name)


def _fill_out_missing_chromecast_info(info: ChromecastInfo) -> ChromecastInfo:
    """Fill out missing attributes of ChromecastInfo using blocking HTTP."""
    if info.is_information_complete:
        # We have all information, no need to check HTTP API. Or this is an
        # audio group, so checking via HTTP won't give us any new information.
        return info

    # Fill out missing information via HTTP dial.
    from pychromecast import dial

    if info.is_audio_group:
        is_dynamic_group = False
        http_group_status = None
        dynamic_groups = []
        if info.uuid:
            http_group_status = dial.get_multizone_status(
                info.host, services=[info.service],
                zconf=ChromeCastZeroconf.get_zeroconf())
            if http_group_status is not None:
                dynamic_groups = \
                    [str(g.uuid) for g in http_group_status.dynamic_groups]
                is_dynamic_group = info.uuid in dynamic_groups

        return ChromecastInfo(
            service=info.service, host=info.host, port=info.port,
            uuid=info.uuid,
            friendly_name=info.friendly_name,
            manufacturer=info.manufacturer,
            model_name=info.model_name,
            is_dynamic_group=is_dynamic_group
        )

    http_device_status = dial.get_device_status(
        info.host, services=[info.service],
        zconf=ChromeCastZeroconf.get_zeroconf())
    if http_device_status is None:
        # HTTP dial didn't give us any new information.
        return info

    return ChromecastInfo(
        service=info.service, host=info.host, port=info.port,
        uuid=(info.uuid or http_device_status.uuid),
        friendly_name=(info.friendly_name or http_device_status.friendly_name),
        manufacturer=(info.manufacturer or http_device_status.manufacturer),
        model_name=(info.model_name or http_device_status.model_name)
    )


def _discover_chromecast(hass: HomeAssistantType, info: ChromecastInfo):
    if info in hass.data[KNOWN_CHROMECAST_INFO_KEY]:
        _LOGGER.debug("Discovered previous chromecast %s", info)

    # Either discovered completely new chromecast or a "moved" one.
    info = _fill_out_missing_chromecast_info(info)
    _LOGGER.debug("Discovered chromecast %s", info)

    if info.uuid is not None:
        # Remove previous cast infos with same uuid from known chromecasts.
        same_uuid = set(x for x in hass.data[KNOWN_CHROMECAST_INFO_KEY]
                        if info.uuid == x.uuid)
        hass.data[KNOWN_CHROMECAST_INFO_KEY] -= same_uuid

    hass.data[KNOWN_CHROMECAST_INFO_KEY].add(info)
    dispatcher_send(hass, SIGNAL_CAST_DISCOVERED, info)


def _remove_chromecast(hass: HomeAssistantType, info: ChromecastInfo):
    # Removed chromecast
    _LOGGER.debug("Removed chromecast %s", info)

    dispatcher_send(hass, SIGNAL_CAST_REMOVED, info)


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


def _setup_internal_discovery(hass: HomeAssistantType) -> None:
    """Set up the pychromecast internal discovery."""
    if INTERNAL_DISCOVERY_RUNNING_KEY not in hass.data:
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY] = threading.Lock()

    if not hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].acquire(blocking=False):
        # Internal discovery is already running
        return

    import pychromecast

    def internal_add_callback(name):
        """Handle zeroconf discovery of a new chromecast."""
        mdns = listener.services[name]
        _discover_chromecast(hass, ChromecastInfo(
            service=name,
            host=mdns[0],
            port=mdns[1],
            uuid=mdns[2],
            model_name=mdns[3],
            friendly_name=mdns[4],
        ))

    def internal_remove_callback(name, mdns):
        """Handle zeroconf discovery of a removed chromecast."""
        _remove_chromecast(hass, ChromecastInfo(
            service=name,
            host=mdns[0],
            port=mdns[1],
            uuid=mdns[2],
            model_name=mdns[3],
            friendly_name=mdns[4],
        ))

    _LOGGER.debug("Starting internal pychromecast discovery.")
    listener, browser = pychromecast.start_discovery(internal_add_callback,
                                                     internal_remove_callback)
    ChromeCastZeroconf.set_zeroconf(browser.zc)

    def stop_discovery(event):
        """Stop discovery of new chromecasts."""
        _LOGGER.debug("Stopping internal pychromecast discovery.")
        pychromecast.stop_discovery(browser)
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].release()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_discovery)


@callback
def _async_create_cast_device(hass: HomeAssistantType,
                              info: ChromecastInfo):
    """Create a CastDevice Entity from the chromecast object.

    Returns None if the cast device has already been added.
    """
    _LOGGER.debug("_async_create_cast_device: %s", info)
    if info.uuid is None:
        # Found a cast without UUID, we don't store it because we won't be able
        # to update it anyway.
        return CastDevice(info)

    # Found a cast with UUID
    if info.is_dynamic_group:
        # This is a dynamic group, do not add it.
        return None

    added_casts = hass.data[ADDED_CAST_DEVICES_KEY]
    if info.uuid in added_casts:
        # Already added this one, the entity will take care of moved hosts
        # itself
        return None
    # -> New cast device
    added_casts.add(info.uuid)
    return CastDevice(info)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up thet Cast platform.

    Deprecated.
    """
    _LOGGER.warning(
        'Setting configuration for Cast via platform is deprecated. '
        'Configure via Cast component instead.')
    await _async_setup_platform(
        hass, config, async_add_entities, discovery_info)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Cast from a config entry."""
    config = hass.data[CAST_DOMAIN].get('media_player', {})
    if not isinstance(config, list):
        config = [config]

    # no pending task
    done, _ = await asyncio.wait([
        _async_setup_platform(hass, cfg, async_add_entities, None)
        for cfg in config])
    if any([task.exception() for task in done]):
        exceptions = [task.exception() for task in done]
        for exception in exceptions:
            _LOGGER.debug("Failed to setup chromecast", exc_info=exception)
        raise PlatformNotReady


async def _async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                                async_add_entities, discovery_info):
    """Set up the cast platform."""
    import pychromecast

    # Import CEC IGNORE attributes
    pychromecast.IGNORE_CEC += config.get(CONF_IGNORE_CEC, [])
    hass.data.setdefault(ADDED_CAST_DEVICES_KEY, set())
    hass.data.setdefault(KNOWN_CHROMECAST_INFO_KEY, set())

    info = None
    if discovery_info is not None:
        info = ChromecastInfo(host=discovery_info['host'],
                              port=discovery_info['port'])
    elif CONF_HOST in config:
        info = ChromecastInfo(host=config[CONF_HOST],
                              port=DEFAULT_PORT)

    @callback
    def async_cast_discovered(discover: ChromecastInfo) -> None:
        """Handle discovery of a new chromecast."""
        if info is not None and info.host_port != discover.host_port:
            # Not our requested cast device.
            return

        cast_device = _async_create_cast_device(hass, discover)
        if cast_device is not None:
            async_add_entities([cast_device])

    async_dispatcher_connect(
        hass, SIGNAL_CAST_DISCOVERED, async_cast_discovered)
    # Re-play the callback for all past chromecasts, store the objects in
    # a list to avoid concurrent modification resulting in exception.
    for chromecast in list(hass.data[KNOWN_CHROMECAST_INFO_KEY]):
        async_cast_discovered(chromecast)

    if info is None or info.is_audio_group:
        # If we were a) explicitly told to enable discovery or
        # b) have an audio group cast device, we need internal discovery.
        hass.async_add_job(_setup_internal_discovery, hass)
    else:
        info = await hass.async_add_job(_fill_out_missing_chromecast_info,
                                        info)
        if info.friendly_name is None:
            _LOGGER.debug("Cannot retrieve detail information for chromecast"
                          " %s, the device may not be online", info)

        hass.async_add_job(_discover_chromecast, hass, info)


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
        chromecast.socket_client.media_controller.register_status_listener(
            self)
        chromecast.register_connection_listener(self)
        # pylint: disable=protected-access
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
        pass

    def removed_from_multizone(self, group_uuid):
        """Handle the cast removed from a group."""
        if self._valid:
            self._cast_device.multizone_new_media_status(group_uuid, None)

    def multizone_new_cast_status(self, group_uuid, cast_status):
        """Handle reception of a new CastStatus for a group."""
        pass

    def multizone_new_media_status(self, group_uuid, media_status):
        """Handle reception of a new MediaStatus for a group."""
        if self._valid:
            self._cast_device.multizone_new_media_status(
                group_uuid, media_status)

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


class DynamicGroupCastStatusListener:
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
        chromecast.socket_client.media_controller.register_status_listener(
            self)
        chromecast.register_connection_listener(self)
        self._mz_mgr.add_multizone(chromecast)

    def new_cast_status(self, cast_status):
        """Handle reception of a new CastStatus."""
        pass

    def new_media_status(self, media_status):
        """Handle reception of a new MediaStatus."""
        if self._valid:
            self._cast_device.new_dynamic_group_media_status(media_status)

    def new_connection_status(self, connection_status):
        """Handle reception of a new ConnectionStatus."""
        if self._valid:
            self._cast_device.new_dynamic_group_connection_status(
                connection_status)

    def invalidate(self):
        """Invalidate this status listener.

        All following callbacks won't be forwarded.
        """
        self._mz_mgr.remove_multizone(self._uuid)
        self._valid = False


class CastDevice(MediaPlayerDevice):
    """Representation of a Cast device on the network.

    This class is the holder of the pychromecast.Chromecast object and its
    socket client. It therefore handles all reconnects and audio group changing
    "elected leader" itself.
    """

    def __init__(self, cast_info):
        """Initialize the cast device."""
        import pychromecast  # noqa: pylint: disable=unused-import
        self._cast_info = cast_info  # type: ChromecastInfo
        self.services = None
        if cast_info.service:
            self.services = set()
            self.services.add(cast_info.service)
        self._chromecast = None  # type: Optional[pychromecast.Chromecast]
        self.cast_status = None
        self.media_status = None
        self.media_status_received = None
        self._dynamic_group_cast_info = None  # type: ChromecastInfo
        self._dynamic_group_cast = None \
            # type: Optional[pychromecast.Chromecast]
        self.dynamic_group_media_status = None
        self.dynamic_group_media_status_received = None
        self.mz_media_status = {}
        self.mz_media_status_received = {}
        self.mz_mgr = None
        self._available = False  # type: bool
        self._dynamic_group_available = False  # type: bool
        self._status_listener = None  # type: Optional[CastStatusListener]
        self._dynamic_group_status_listener = None \
            # type: Optional[DynamicGroupCastStatusListener]
        self._add_remove_handler = None
        self._del_remove_handler = None

    async def async_added_to_hass(self):
        """Create chromecast object when added to hass."""
        @callback
        def async_cast_discovered(discover: ChromecastInfo):
            """Handle discovery of new Chromecast."""
            if self._cast_info.uuid is None:
                # We can't handle empty UUIDs
                return
            if _is_matching_dynamic_group(self._cast_info, discover):
                _LOGGER.debug("Discovered matching dynamic group: %s",
                              discover)
                self.hass.async_create_task(
                    self.async_set_dynamic_group(discover))
                return

            if self._cast_info.uuid != discover.uuid:
                # Discovered is not our device.
                return
            if self.services is None:
                _LOGGER.warning(
                    "[%s %s (%s:%s)] Received update for manually added Cast",
                    self.entity_id, self._cast_info.friendly_name,
                    self._cast_info.host, self._cast_info.port)
                return
            _LOGGER.debug("Discovered chromecast with same UUID: %s", discover)
            self.hass.async_create_task(self.async_set_cast_info(discover))

        def async_cast_removed(discover: ChromecastInfo):
            """Handle removal of Chromecast."""
            if self._cast_info.uuid is None:
                # We can't handle empty UUIDs
                return
            if (self._dynamic_group_cast_info is not None and
                    self._dynamic_group_cast_info.uuid == discover.uuid):
                _LOGGER.debug("Removed matching dynamic group: %s", discover)
                self.hass.async_create_task(self.async_del_dynamic_group())
                return
            if self._cast_info.uuid != discover.uuid:
                # Removed is not our device.
                return
            _LOGGER.debug("Removed chromecast with same UUID: %s", discover)
            self.hass.async_create_task(self.async_del_cast_info(discover))

        async def async_stop(event):
            """Disconnect socket on Home Assistant stop."""
            await self._async_disconnect()

        self._add_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_CAST_DISCOVERED,
            async_cast_discovered)
        self._del_remove_handler = async_dispatcher_connect(
            self.hass, SIGNAL_CAST_REMOVED,
            async_cast_removed)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)
        self.hass.async_create_task(self.async_set_cast_info(self._cast_info))
        for info in self.hass.data[KNOWN_CHROMECAST_INFO_KEY]:
            if _is_matching_dynamic_group(self._cast_info, info):
                _LOGGER.debug("[%s %s (%s:%s)] Found dynamic group: %s",
                              self.entity_id, self._cast_info.friendly_name,
                              self._cast_info.host, self._cast_info.port, info)
                self.hass.async_create_task(
                    self.async_set_dynamic_group(info))
                break

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect Chromecast object when removed."""
        await self._async_disconnect()
        if self._cast_info.uuid is not None:
            # Remove the entity from the added casts so that it can dynamically
            # be re-added again.
            self.hass.data[ADDED_CAST_DEVICES_KEY].remove(self._cast_info.uuid)
        if self._add_remove_handler:
            self._add_remove_handler()
        if self._del_remove_handler:
            self._del_remove_handler()

    async def async_set_cast_info(self, cast_info):
        """Set the cast information and set up the chromecast object."""
        import pychromecast
        self._cast_info = cast_info

        if self.services is not None:
            if cast_info.service not in self.services:
                _LOGGER.debug("[%s %s (%s:%s)] Got new service: %s (%s)",
                              self.entity_id, self._cast_info.friendly_name,
                              self._cast_info.host, self._cast_info.port,
                              cast_info.service, self.services)

            self.services.add(cast_info.service)

        if self._chromecast is not None:
            # Only setup the chromecast once, added elements to services
            # will automatically be picked up.
            return

        # pylint: disable=protected-access
        if self.services is None:
            _LOGGER.debug(
                "[%s %s (%s:%s)] Connecting to cast device by host %s",
                self.entity_id, self._cast_info.friendly_name,
                self._cast_info.host, self._cast_info.port, cast_info)
            chromecast = await self.hass.async_add_job(
                pychromecast._get_chromecast_from_host, (
                    cast_info.host, cast_info.port, cast_info.uuid,
                    cast_info.model_name, cast_info.friendly_name
                ))
        else:
            _LOGGER.debug(
                "[%s %s (%s:%s)] Connecting to cast device by service %s",
                self.entity_id, self._cast_info.friendly_name,
                self._cast_info.host, self._cast_info.port, self.services)
            chromecast = await self.hass.async_add_job(
                pychromecast._get_chromecast_from_service, (
                    self.services, ChromeCastZeroconf.get_zeroconf(),
                    cast_info.uuid, cast_info.model_name,
                    cast_info.friendly_name
                ))
        self._chromecast = chromecast

        if CAST_MULTIZONE_MANAGER_KEY not in self.hass.data:
            from pychromecast.controllers.multizone import MultizoneManager
            self.hass.data[CAST_MULTIZONE_MANAGER_KEY] = MultizoneManager()
        self.mz_mgr = self.hass.data[CAST_MULTIZONE_MANAGER_KEY]

        self._status_listener = CastStatusListener(
            self, chromecast, self.mz_mgr)
        self._available = False
        self.cast_status = chromecast.status
        self.media_status = chromecast.media_controller.status
        self._chromecast.start()
        self.async_schedule_update_ha_state()

    async def async_del_cast_info(self, cast_info):
        """Remove the service."""
        self.services.discard(cast_info.service)
        _LOGGER.debug("[%s %s (%s:%s)] Remove service: %s (%s)",
                      self.entity_id, self._cast_info.friendly_name,
                      self._cast_info.host, self._cast_info.port,
                      cast_info.service, self.services)

    async def async_set_dynamic_group(self, cast_info):
        """Set the cast information and set up the chromecast object."""
        import pychromecast
        _LOGGER.debug(
            "[%s %s (%s:%s)] Connecting to dynamic group by host %s",
            self.entity_id, self._cast_info.friendly_name,
            self._cast_info.host, self._cast_info.port, cast_info)

        self.async_del_dynamic_group()
        self._dynamic_group_cast_info = cast_info

        # pylint: disable=protected-access
        chromecast = await self.hass.async_add_executor_job(
            pychromecast._get_chromecast_from_host, (
                cast_info.host, cast_info.port, cast_info.uuid,
                cast_info.model_name, cast_info.friendly_name
            ))

        self._dynamic_group_cast = chromecast

        if CAST_MULTIZONE_MANAGER_KEY not in self.hass.data:
            from pychromecast.controllers.multizone import MultizoneManager
            self.hass.data[CAST_MULTIZONE_MANAGER_KEY] = MultizoneManager()
        mz_mgr = self.hass.data[CAST_MULTIZONE_MANAGER_KEY]

        self._dynamic_group_status_listener = DynamicGroupCastStatusListener(
            self, chromecast, mz_mgr)
        self._dynamic_group_available = False
        self.dynamic_group_media_status = chromecast.media_controller.status
        self._dynamic_group_cast.start()
        self.async_schedule_update_ha_state()

    async def async_del_dynamic_group(self):
        """Remove the dynamic group."""
        cast_info = self._dynamic_group_cast_info
        _LOGGER.debug("[%s %s (%s:%s)] Remove dynamic group: %s",
                      self.entity_id, self._cast_info.friendly_name,
                      self._cast_info.host, self._cast_info.port,
                      cast_info.service if cast_info else None)

        self._dynamic_group_available = False
        self._dynamic_group_cast_info = None
        if self._dynamic_group_cast is not None:
            await self.hass.async_add_executor_job(
                self._dynamic_group_cast.disconnect)

        self._dynamic_group_invalidate()

        self.async_schedule_update_ha_state()

    async def _async_disconnect(self):
        """Disconnect Chromecast object if it is set."""
        if self._chromecast is None:
            # Can't disconnect if not connected.
            return
        _LOGGER.debug("[%s %s (%s:%s)] Disconnecting from chromecast socket.",
                      self.entity_id, self._cast_info.friendly_name,
                      self._cast_info.host, self._cast_info.port)
        self._available = False
        self.async_schedule_update_ha_state()

        await self.hass.async_add_executor_job(self._chromecast.disconnect)
        if self._dynamic_group_cast is not None:
            await self.hass.async_add_executor_job(
                self._dynamic_group_cast.disconnect)

        self._invalidate()

        self.async_schedule_update_ha_state()

    def _invalidate(self):
        """Invalidate some attributes."""
        self._chromecast = None
        self.cast_status = None
        self.media_status = None
        self.media_status_received = None
        self.mz_media_status = {}
        self.mz_media_status_received = {}
        self.mz_mgr = None
        if self._status_listener is not None:
            self._status_listener.invalidate()
            self._status_listener = None

    def _dynamic_group_invalidate(self):
        """Invalidate some attributes."""
        self._dynamic_group_cast = None
        self.dynamic_group_media_status = None
        self.dynamic_group_media_status_received = None
        if self._dynamic_group_status_listener is not None:
            self._dynamic_group_status_listener.invalidate()
            self._dynamic_group_status_listener = None

    # ========== Callbacks ==========
    def new_cast_status(self, cast_status):
        """Handle updates of the cast status."""
        self.cast_status = cast_status
        self.schedule_update_ha_state()

    def new_media_status(self, media_status):
        """Handle updates of the media status."""
        self.media_status = media_status
        self.media_status_received = dt_util.utcnow()
        self.schedule_update_ha_state()

    def new_connection_status(self, connection_status):
        """Handle updates of connection status."""
        from pychromecast.socket_client import CONNECTION_STATUS_CONNECTED, \
            CONNECTION_STATUS_DISCONNECTED

        _LOGGER.debug(
            "[%s %s (%s:%s)] Received cast device connection status: %s",
            self.entity_id, self._cast_info.friendly_name,
            self._cast_info.host, self._cast_info.port,
            connection_status.status)
        if connection_status.status == CONNECTION_STATUS_DISCONNECTED:
            self._available = False
            self._invalidate()
            self.schedule_update_ha_state()
            return

        new_available = connection_status.status == CONNECTION_STATUS_CONNECTED
        if new_available != self._available:
            # Connection status callbacks happen often when disconnected.
            # Only update state when availability changed to put less pressure
            # on state machine.
            _LOGGER.debug(
                "[%s %s (%s:%s)] Cast device availability changed: %s",
                self.entity_id, self._cast_info.friendly_name,
                self._cast_info.host, self._cast_info.port,
                connection_status.status)
            info = self._cast_info
            if info.friendly_name is None and not info.is_audio_group:
                # We couldn't find friendly_name when the cast was added, retry
                self._cast_info = _fill_out_missing_chromecast_info(info)
            self._available = new_available
            self.schedule_update_ha_state()

    def new_dynamic_group_media_status(self, media_status):
        """Handle updates of the media status."""
        self.dynamic_group_media_status = media_status
        self.dynamic_group_media_status_received = dt_util.utcnow()
        self.schedule_update_ha_state()

    def new_dynamic_group_connection_status(self, connection_status):
        """Handle updates of connection status."""
        from pychromecast.socket_client import CONNECTION_STATUS_CONNECTED, \
            CONNECTION_STATUS_DISCONNECTED

        _LOGGER.debug(
            "[%s %s (%s:%s)] Received dynamic group connection status: %s",
            self.entity_id, self._cast_info.friendly_name,
            self._cast_info.host, self._cast_info.port,
            connection_status.status)
        if connection_status.status == CONNECTION_STATUS_DISCONNECTED:
            self._dynamic_group_available = False
            self._dynamic_group_invalidate()
            self.schedule_update_ha_state()
            return

        new_available = connection_status.status == CONNECTION_STATUS_CONNECTED
        if new_available != self._dynamic_group_available:
            # Connection status callbacks happen often when disconnected.
            # Only update state when availability changed to put less pressure
            # on state machine.
            _LOGGER.debug(
                "[%s %s (%s:%s)] Dynamic group availability changed: %s",
                self.entity_id, self._cast_info.friendly_name,
                self._cast_info.host, self._cast_info.port,
                connection_status.status)
            self._dynamic_group_available = new_available
            self.schedule_update_ha_state()

    def multizone_new_media_status(self, group_uuid, media_status):
        """Handle updates of audio group media status."""
        _LOGGER.debug(
            "[%s %s (%s:%s)] Multizone %s media status: %s",
            self.entity_id, self._cast_info.friendly_name,
            self._cast_info.host, self._cast_info.port,
            group_uuid, media_status)
        self.mz_media_status[group_uuid] = media_status
        self.mz_media_status_received[group_uuid] = dt_util.utcnow()
        self.schedule_update_ha_state()

    # ========== Service Calls ==========
    def _media_controller(self):
        """
        Return media status.

        First try from our own cast, then dynamic groups and finally
        groups which our cast is a member in.
        """
        media_status = self.media_status
        media_controller = self._chromecast.media_controller

        if ((media_status is None or media_status.player_state == "UNKNOWN")
                and self._dynamic_group_cast is not None):
            media_status = self.dynamic_group_media_status
            media_controller = \
                self._dynamic_group_cast.media_controller

        if media_status is None or media_status.player_state == "UNKNOWN":
            groups = self.mz_media_status
            for k, val in groups.items():
                if val and val.player_state != "UNKNOWN":
                    media_controller = \
                        self.mz_mgr.get_multizone_mediacontroller(k)
                    break

        return media_controller

    def turn_on(self):
        """Turn on the cast device."""
        import pychromecast

        if not self._chromecast.is_idle:
            # Already turned on
            return

        if self._chromecast.app_id is not None:
            # Quit the previous app before starting splash screen
            self._chromecast.quit_app()

        # The only way we can turn the Chromecast is on is by launching an app
        self._chromecast.play_media(CAST_SPLASH,
                                    pychromecast.STREAM_TYPE_BUFFERED)

    def turn_off(self):
        """Turn off the cast device."""
        self._chromecast.quit_app()

    def mute_volume(self, mute):
        """Mute the volume."""
        self._chromecast.set_volume_muted(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._chromecast.set_volume(volume)

    def media_play(self):
        """Send play command."""
        media_controller = self._media_controller()
        media_controller.play()

    def media_pause(self):
        """Send pause command."""
        media_controller = self._media_controller()
        media_controller.pause()

    def media_stop(self):
        """Send stop command."""
        media_controller = self._media_controller()
        media_controller.stop()

    def media_previous_track(self):
        """Send previous track command."""
        media_controller = self._media_controller()
        media_controller.queue_prev()

    def media_next_track(self):
        """Send next track command."""
        media_controller = self._media_controller()
        media_controller.queue_next()

    def media_seek(self, position):
        """Seek the media to a specific location."""
        media_controller = self._media_controller()
        media_controller.seek(position)

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL."""
        # We do not want this to be forwarded to a group / dynamic group
        self._chromecast.media_controller.play_media(media_id, media_type)

    # ========== Properties ==========
    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._cast_info.friendly_name

    @property
    def device_info(self):
        """Return information about the device."""
        cast_info = self._cast_info

        if cast_info.model_name == "Google Cast Group":
            return None

        return {
            'name': cast_info.friendly_name,
            'identifiers': {
                (CAST_DOMAIN, cast_info.uuid.replace('-', ''))
            },
            'model': cast_info.model_name,
            'manufacturer': cast_info.manufacturer,
        }

    def _media_status(self):
        """
        Return media status.

        First try from our own cast, then dynamic groups and finally
        groups which our cast is a member in.
        """
        media_status = self.media_status
        media_status_received = self.media_status_received

        if ((media_status is None or media_status.player_state == "UNKNOWN")
                and self._dynamic_group_cast is not None):
            media_status = self.dynamic_group_media_status
            media_status_received = self.dynamic_group_media_status_received

        if media_status is None or media_status.player_state == "UNKNOWN":
            groups = self.mz_media_status
            for k, val in groups.items():
                if val and val.player_state != "UNKNOWN":
                    media_status = val
                    media_status_received = self.mz_media_status_received[k]
                    break

        return (media_status, media_status_received)

    @property
    def state(self):
        """Return the state of the player."""
        media_status, _ = self._media_status()

        if media_status is None:
            return None
        if media_status.player_is_playing:
            return STATE_PLAYING
        if media_status.player_is_paused:
            return STATE_PAUSED
        if media_status.player_is_idle:
            return STATE_IDLE
        if self._chromecast is not None and self._chromecast.is_idle:
            return STATE_OFF
        return None

    @property
    def available(self):
        """Return True if the cast device is connected."""
        return self._available

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self.cast_status.volume_level if self.cast_status else None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.cast_status.volume_muted if self.cast_status else None

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        media_status, _ = self._media_status()
        return media_status.content_id if media_status else None

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        media_status, _ = self._media_status()
        if media_status is None:
            return None
        if media_status.media_is_tvshow:
            return MEDIA_TYPE_TVSHOW
        if media_status.media_is_movie:
            return MEDIA_TYPE_MOVIE
        if media_status.media_is_musictrack:
            return MEDIA_TYPE_MUSIC
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        media_status, _ = self._media_status()
        return media_status.duration if media_status else None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        media_status, _ = self._media_status()
        if media_status is None:
            return None

        images = media_status.images

        return images[0].url if images and images[0].url else None

    @property
    def media_title(self):
        """Title of current playing media."""
        media_status, _ = self._media_status()
        return media_status.title if media_status else None

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        media_status, _ = self._media_status()
        return media_status.artist if media_status else None

    @property
    def media_album_name(self):
        """Album of current playing media (Music track only)."""
        media_status, _ = self._media_status()
        return media_status.album_name if media_status else None

    @property
    def media_album_artist(self):
        """Album artist of current playing media (Music track only)."""
        media_status, _ = self._media_status()
        return media_status.album_artist if media_status else None

    @property
    def media_track(self):
        """Track number of current playing media (Music track only)."""
        media_status, _ = self._media_status()
        return media_status.track if media_status else None

    @property
    def media_series_title(self):
        """Return the title of the series of current playing media."""
        media_status, _ = self._media_status()
        return media_status.series_title if media_status else None

    @property
    def media_season(self):
        """Season of current playing media (TV Show only)."""
        media_status, _ = self._media_status()
        return media_status.season if media_status else None

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        media_status, _ = self._media_status()
        return media_status.episode if media_status else None

    @property
    def app_id(self):
        """Return the ID of the current running app."""
        return self._chromecast.app_id if self._chromecast else None

    @property
    def app_name(self):
        """Name of the current running app."""
        return self._chromecast.app_display_name if self._chromecast else None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        support = SUPPORT_CAST
        media_status, _ = self._media_status()

        if media_status:
            if media_status.supports_queue_next:
                support |= SUPPORT_PREVIOUS_TRACK
            if media_status.supports_queue_next:
                support |= SUPPORT_NEXT_TRACK
            if media_status.supports_seek:
                support |= SUPPORT_SEEK

        return support

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        media_status, _ = self._media_status()
        if media_status is None or \
            not (media_status.player_is_playing or
                 media_status.player_is_paused or
                 media_status.player_is_idle):
            return None
        return media_status.current_time

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        _, media_status_recevied = self._media_status()
        return media_status_recevied

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._cast_info.uuid
