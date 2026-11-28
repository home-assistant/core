"""Class to hold remote accessories."""

from abc import ABC, abstractmethod
import logging
from typing import Any, override

from pyhap.const import CATEGORY_TELEVISION
from pyhap.service import Service

from homeassistant.components.remote import (
    DOMAIN as REMOTE_DOMAIN,
    RemoteEntityFeature,
    RemoteEntityStateAttribute,
    RemoteService,
    RemoteServiceArgument,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityStateAttribute,
    TargetKey,
)
from homeassistant.core import State, callback

from .accessories import TYPES, HomeAccessory
from .const import (
    ATTR_KEY_NAME,
    CHAR_ACTIVE,
    CHAR_ACTIVE_IDENTIFIER,
    CHAR_CONFIGURED_NAME,
    CHAR_CURRENT_VISIBILITY_STATE,
    CHAR_IDENTIFIER,
    CHAR_INPUT_SOURCE_TYPE,
    CHAR_IS_CONFIGURED,
    CHAR_NAME,
    CHAR_REMOTE_KEY,
    CHAR_SLEEP_DISCOVER_MODE,
    EVENT_HOMEKIT_TV_REMOTE_KEY_PRESSED,
    KEY_ARROW_DOWN,
    KEY_ARROW_LEFT,
    KEY_ARROW_RIGHT,
    KEY_ARROW_UP,
    KEY_BACK,
    KEY_EXIT,
    KEY_FAST_FORWARD,
    KEY_INFORMATION,
    KEY_NEXT_TRACK,
    KEY_PLAY_PAUSE,
    KEY_PREVIOUS_TRACK,
    KEY_REWIND,
    KEY_SELECT,
    SERV_INPUT_SOURCE,
    SERV_TELEVISION,
)
from .util import cleanup_name_for_homekit

MAXIMUM_SOURCES = (
    90  # Maximum services per accessory is 100. The base acccessory uses 9
)

_LOGGER = logging.getLogger(__name__)

INPUT_SOURCE_TYPE_OTHER = 0
INPUT_SOURCE_TYPE_HDMI = 3

REMOTE_KEYS = {
    0: KEY_REWIND,
    1: KEY_FAST_FORWARD,
    2: KEY_NEXT_TRACK,
    3: KEY_PREVIOUS_TRACK,
    4: KEY_ARROW_UP,
    5: KEY_ARROW_DOWN,
    6: KEY_ARROW_LEFT,
    7: KEY_ARROW_RIGHT,
    8: KEY_SELECT,
    9: KEY_BACK,
    10: KEY_EXIT,
    11: KEY_PLAY_PAUSE,
    15: KEY_INFORMATION,
}


def _input_source_type(source: str) -> int:
    """Return the HomeKit input source type for a source name."""
    if "hdmi" in source.lower():
        return INPUT_SOURCE_TYPE_HDMI
    return INPUT_SOURCE_TYPE_OTHER


def _map_sources(source_list: list[str]) -> dict[str, str]:
    """Return a dict of sources mapped to their homekit safe name."""
    return {cleanup_name_for_homekit(source): source for source in source_list}


class RemoteInputSelectAccessory(HomeAccessory, ABC):
    """Generate a InputSelect accessory."""

    def __init__(
        self,
        required_feature: int,
        source_key: str,
        source_list_key: str,
        *args: Any,
        category: int = CATEGORY_TELEVISION,
        **kwargs: Any,
    ) -> None:
        """Initialize a InputSelect accessory object."""
        super().__init__(*args, category=category, **kwargs)
        state = self.hass.states.get(self.entity_id)
        assert state
        features = state.attributes.get(EntityStateAttribute.SUPPORTED_FEATURES, 0)
        self._mapped_sources_list: list[str] = []
        self._mapped_sources: dict[str, str] = {}
        self.source_key = source_key
        self.source_list_key = source_list_key
        self.sources = []
        self.support_select_source = False
        if features & required_feature:
            sources = self._get_ordered_source_list_from_state(state)
            if len(sources) > MAXIMUM_SOURCES:
                _LOGGER.warning(
                    "%s: Reached maximum number of sources (%s)",
                    self.entity_id,
                    MAXIMUM_SOURCES,
                )
            self.sources = sources[:MAXIMUM_SOURCES]
            if self.sources:
                self.support_select_source = True
        if not self.support_select_source:
            # Without inputs to rename, new sources need a new accessory
            self._reload_on_change_attrs.append(source_list_key)
        self._input_services: list[Service] = []
        self._reload_requested = False

        self.chars_tv = [CHAR_REMOTE_KEY]
        serv_tv = self.serv_tv = self.add_preload_service(
            SERV_TELEVISION, self.chars_tv
        )
        self.char_remote_key = self.serv_tv.configure_char(
            CHAR_REMOTE_KEY, setter_callback=self.set_remote_key
        )
        self.set_primary_service(serv_tv)
        serv_tv.configure_char(CHAR_CONFIGURED_NAME, value=self.display_name)
        serv_tv.configure_char(CHAR_SLEEP_DISCOVER_MODE, value=True)
        self.char_active = serv_tv.configure_char(
            CHAR_ACTIVE, setter_callback=self.set_on_off
        )

        if not self.support_select_source:
            return

        self.char_input_source = serv_tv.configure_char(
            CHAR_ACTIVE_IDENTIFIER, setter_callback=self.set_input_source
        )
        for index, source in enumerate(self.sources):
            serv_input = self.add_preload_service(
                SERV_INPUT_SOURCE, [CHAR_IDENTIFIER, CHAR_NAME], unique_id=source
            )
            serv_tv.add_linked_service(serv_input)
            self._input_services.append(serv_input)
            serv_input.configure_char(CHAR_CONFIGURED_NAME, value=source)
            serv_input.configure_char(CHAR_NAME, value=source)
            serv_input.configure_char(CHAR_IDENTIFIER, value=index)
            serv_input.configure_char(CHAR_IS_CONFIGURED, value=True)
            serv_input.configure_char(
                CHAR_INPUT_SOURCE_TYPE, value=_input_source_type(source)
            )
            serv_input.configure_char(CHAR_CURRENT_VISIBILITY_STATE, value=False)
            _LOGGER.debug("%s: Added source %s", self.entity_id, source)

    @callback
    def _async_update_sources(self, new_state: State) -> bool:
        """Rename the inputs in place, or rebuild when their number changes.

        Rebuilding the accessory changes its configuration number, and the
        Home app may keep showing the old inputs until it is restarted.
        Return True when the accessory is being rebuilt.
        """
        # Keep the current mapping until the inputs match the new sources, so
        # an input selected in HomeKit until then still maps to its source
        mapped_sources = _map_sources(
            new_state.attributes.get(self.source_list_key, [])
        )
        sources = list(mapped_sources)[:MAXIMUM_SOURCES]
        if len(sources) != len(self.sources):
            if not self._reload_requested:
                self._reload_requested = True
                _LOGGER.debug(
                    "%s: Number of sources changed. Rebuilding Accessory",
                    self.entity_id,
                )
                self.async_reload()
            return True
        for serv_input, old_source, source in zip(
            self._input_services, self.sources, sources, strict=True
        ):
            if source == old_source:
                continue
            serv_input.get_characteristic(CHAR_CONFIGURED_NAME).set_value(source)
            serv_input.get_characteristic(CHAR_NAME).set_value(source)
            serv_input.get_characteristic(CHAR_INPUT_SOURCE_TYPE).set_value(
                _input_source_type(source)
            )
            _LOGGER.debug(
                "%s: Renamed source %s to %s", self.entity_id, old_source, source
            )
        self.sources = sources
        self._mapped_sources = mapped_sources
        return False

    def _get_mapped_sources(self, state: State) -> dict[str, str]:
        """Return a dict of sources mapped to their homekit safe name."""
        source_list = state.attributes.get(self.source_list_key, [])
        if self._mapped_sources_list != source_list:
            self._mapped_sources = _map_sources(source_list)
        return self._mapped_sources

    def _get_ordered_source_list_from_state(self, state: State) -> list[str]:
        """Return ordered source list while preserving order with duplicates removed.

        Some integrations have duplicate sources in the source list
        which will make the source list conflict as HomeKit requires
        unique source names.
        """
        return list(self._get_mapped_sources(state))

    @abstractmethod
    def set_on_off(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""

    @abstractmethod
    def set_input_source(self, value: int) -> None:
        """Send input set value if call came from HomeKit."""

    @abstractmethod
    def set_remote_key(self, value: int) -> None:
        """Send remote key value if call came from HomeKit."""

    @callback
    def _async_update_input_state(self, hk_state: int, new_state: State) -> None:
        """Update input state after state changed."""
        # Set active input
        if not self.support_select_source or not self.sources:
            return
        # A failed command re-syncs without the availability filter, and an
        # unavailable entity may no longer write its source list
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        if self._async_update_sources(new_state):
            return
        source = new_state.attributes.get(self.source_key)
        source_name = cleanup_name_for_homekit(source)
        _LOGGER.debug("%s: Set current input to %s", self.entity_id, source_name)
        if source_name in self.sources:
            index = self.sources.index(source_name)
            self.char_input_source.set_value(index)
            return

        possible_sources = self._get_ordered_source_list_from_state(new_state)
        if source_name in possible_sources:
            # The sources were just synced, so only those above the maximum are left
            _LOGGER.debug(
                "%s: Source %s and above are not supported",
                self.entity_id,
                MAXIMUM_SOURCES,
            )

        _LOGGER.debug(
            "%s: Source %s does not exist the source list: %s",
            self.entity_id,
            source,
            possible_sources,
        )
        self.char_input_source.set_value(0)


@TYPES.register("ActivityRemote")
class ActivityRemote(RemoteInputSelectAccessory):
    """Generate a Activity Remote accessory."""

    def __init__(self, *args: Any) -> None:
        """Initialize a Activity Remote accessory object."""
        super().__init__(
            RemoteEntityFeature.ACTIVITY,
            RemoteEntityStateAttribute.CURRENT_ACTIVITY,
            RemoteEntityStateAttribute.ACTIVITY_LIST,
            *args,
        )
        state = self.hass.states.get(self.entity_id)
        assert state
        self.async_update_state(state)

    @override
    def set_on_off(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s', self.entity_id, value)
        service = RemoteService.TURN_ON if value else RemoteService.TURN_OFF
        params: dict[str, Any] = {TargetKey.ENTITY_ID: self.entity_id}
        self.async_call_service(REMOTE_DOMAIN, service, params)

    @override
    def set_input_source(self, value: int) -> None:
        """Send input set value if call came from HomeKit."""
        _LOGGER.debug("%s: Set current input to %s", self.entity_id, value)
        source = self._mapped_sources[self.sources[value]]
        params: dict[str, Any] = {
            TargetKey.ENTITY_ID: self.entity_id,
            RemoteServiceArgument.ACTIVITY: source,
        }
        self.async_call_service(REMOTE_DOMAIN, RemoteService.TURN_ON, params)

    @override
    def set_remote_key(self, value: int) -> None:
        """Send remote key value if call came from HomeKit."""
        _LOGGER.debug("%s: Set remote key to %s", self.entity_id, value)
        if (key_name := REMOTE_KEYS.get(value)) is None:
            _LOGGER.warning("%s: Unhandled key press for %s", self.entity_id, value)
            return
        self.hass.bus.async_fire(
            EVENT_HOMEKIT_TV_REMOTE_KEY_PRESSED,
            {ATTR_KEY_NAME: key_name, ATTR_ENTITY_ID: self.entity_id},
        )

    @callback
    @override
    def async_update_state(self, new_state: State) -> None:
        """Update Television remote state after state changed."""
        current_state = new_state.state
        # Power state remote
        hk_state = 1 if current_state == STATE_ON else 0
        _LOGGER.debug("%s: Set current active state to %s", self.entity_id, hk_state)
        self.char_active.set_value(hk_state)

        self._async_update_input_state(hk_state, new_state)
