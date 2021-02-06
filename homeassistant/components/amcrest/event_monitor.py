"""Support for Amcrest/Dahua IP camera events."""
import logging
import re
import threading

from amcrest import AmcrestError

from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    EVENT_ACTION_START,
    EVENT_ACTION_STOP,
    EVENT_KEY_ACTION,
    EVENT_KEY_CODE,
    SERVICE_EVENT,
)
from .helpers import service_signal

_LOGGER = logging.getLogger(__name__)

# Regex to parse event_channel_happened API responses
CHANNEL_HAPPENED_PARSE_PATTERN = re.compile(r"channels\[\d+\]=([\d]+)")

# Regex to strip all non-alphadecimal characters
CLEAN_PATTERN = re.compile(r"(^[\W_]+|[\W_]+$)")


def _clean_str(s):
    return CLEAN_PATTERN.sub("", s)


class EventMonitor:
    """
    Monitor for events coming from an Amcrest/Dahua endpoint.

    Spins up a thread waiting on events from the camera or NVR events
    and transforms/relays those events to HomeAssistant constructs.
    """

    def __init__(self, hass, api, event_codes, channel, name):
        """Initialize an Amcrest EventMonitor."""
        self._api = api
        self._hass = hass

        # Contains a mapping from channel (id) -> (channel) name
        self._channel_name_map = dict()
        # Contains a map event_code -> set(subscribed_channels)
        self._event_code_map = dict()
        self._event_code_map_lock = threading.Lock()

        self.monitor_events(event_codes, channel, name)
        thread = threading.Thread(
            target=self._worker_thread_main,
            name=f"Amcrest EventMonitor [{api._host}]",
            args=(),
            daemon=True,
        )
        thread.start()

    def monitor_events(self, event_codes, channel, name):
        """Start monitoring a set of event codes on a given channel for a given HA device name."""
        with self._event_code_map_lock:
            self._channel_name_map[int(channel)] = name
            for code in event_codes:
                if code in self._event_code_map:
                    self._event_code_map[code].add(channel)
                else:
                    self._event_code_map[code] = {channel}
            _LOGGER.debug("Updating event monitor config for %s", self._api._host)
            _LOGGER.debug(
                "Now monitoring events %s for '%s' on channel %d",
                event_codes,
                name,
                channel,
            )

    def _get_channels_for_event(self, event_info):
        """Return a set of channels for which the event occurred."""
        # Event information appears to be truncated by the amcrest lib, missing
        # some information such as the source channel.
        # Making a second API call to determine on which channel the event
        # occurred.
        # If/when fixed, implement extracting the channel info straight out of
        # event_info
        code = event_info[EVENT_KEY_CODE]
        api_result = self._api.event_channels_happened(code)
        return self._parse_event_channel_info(api_result)

    def _parse_event_channel_info(self, api_result):
        """Turn the result of an amcrest event_channels_happened API call into a set of channel indices."""
        channels = re.findall(CHANNEL_HAPPENED_PARSE_PATTERN, api_result)

        # Gotcha! API input channel numbers are 1-based while channel numbers
        # in API responses are 0 based... ಠ_ಠ
        return set(map(lambda x: int(x) + 1, channels))

    def _parse_event_info(self, raw_event):
        """Turn raw event strings from the amcrest lib into a key-value dictionary."""
        event_key_values = raw_event.strip("\r\n").split(";")
        event_info = dict()
        for event_kv in event_key_values:
            try:
                [key, value] = event_kv.split("=")
                event_info[_clean_str(key)] = _clean_str(value)
            except ValueError:
                _LOGGER.warn(
                    "Received invalid/truncated event information, "
                    + "best-effort parsing: %s",
                    raw_event,
                )
        return event_info

    def _worker_process_event(self, raw_event_info, active_events):
        event_info = self._parse_event_info(raw_event_info)
        if EVENT_KEY_ACTION not in event_info:
            _LOGGER.error(
                "Received an event from the camera without a " + "corresponding action"
            )
            return
        if EVENT_KEY_CODE not in event_info:
            _LOGGER.error(
                "Received an event from the camera without a " + "corresponding code"
            )
            return

        action = event_info[EVENT_KEY_ACTION]
        code = event_info[EVENT_KEY_CODE]

        if action == EVENT_ACTION_START:
            with self._event_code_map_lock:
                channels_subscribed = self._event_code_map[code]
            channels_occurred = self._get_channels_for_event(event_info)
            _LOGGER.debug(
                "Event %s started on channels %s, %s subscribed",
                code,
                channels_occurred,
                channels_subscribed,
            )
            channels_of_interest = channels_occurred.intersection(channels_subscribed)

            if code not in active_events:
                active_events[code] = set()

            for channel in channels_of_interest:
                # Check whether the event is new for this channel or if we've
                # already been notified of it
                if channel not in active_events[code]:
                    active_events[code].add(channel)
                    name = self._channel_name_map[channel]
                    signal = service_signal(SERVICE_EVENT, name, code)
                    dispatcher_send(self._hass, signal, event_info)

        elif action == EVENT_ACTION_STOP:
            channels_still_active = self._get_channels_for_event(event_info)
            if code in active_events:
                channels_inactive = set()
                for channel in active_events[code]:
                    _LOGGER.debug("Event %s stopped on channel %d", code, channel)
                    # If the channel was active but not found in
                    # channels_still_active then the event stopped
                    if channel not in channels_still_active:
                        channels_inactive.add(channel)
                        name = self._channel_name_map[channel]
                        signal = service_signal(SERVICE_EVENT, name, code)
                        dispatcher_send(self._hass, signal, event_info)
                for stopped in channels_inactive:
                    active_events[code].remove(stopped)

    def _worker_thread_main(self):
        _LOGGER.debug("Event monitor worker thread starting for: %s", self._api._host)

        # Keeps track of which events are active on which channels
        active_events = dict()

        while True:
            self._api.available_flag.wait()
            try:
                with self._event_code_map_lock:
                    event_codes = ",".join(self._event_code_map.keys())
                _LOGGER.debug("Scanning for events: %s", event_codes)

                for raw_event_info in self._api.event_stream(
                    event_codes, retries=5, timeout_cmd=None
                ):
                    self._worker_process_event(raw_event_info, active_events)
            except AmcrestError as error:
                _LOGGER.warning("Error while processing camera events: %r", error)
