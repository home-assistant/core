"""Class to hold remote accessories."""
from abc import ABC, abstractmethod
import logging
from typing import Any

from pyhap.const import CATEGORY_TELEVISION

from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_ACTIVITY_LIST,
    ATTR_CURRENT_ACTIVITY,
    DOMAIN as REMOTE_DOMAIN,
    RemoteEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
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
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        self._reload_on_change_attrs.extend((source_list_key,))
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
            serv_input.configure_char(CHAR_CONFIGURED_NAME, value=source)
            serv_input.configure_char(CHAR_NAME, value=source)
            serv_input.configure_char(CHAR_IDENTIFIER, value=index)
            serv_input.configure_char(CHAR_IS_CONFIGURED, value=True)
            input_type = 3 if "hdmi" in source.lower() else 0
            serv_input.configure_char(CHAR_INPUT_SOURCE_TYPE, value=input_type)
            serv_input.configure_char(CHAR_CURRENT_VISIBILITY_STATE, value=False)
            _LOGGER.debug("%s: Added source %s", self.entity_id, source)

    def _get_mapped_sources(self, state: State) -> dict[str, str]:
        """Return a dict of sources mapped to their homekit safe name."""
        source_list = state.attributes.get(self.source_list_key, [])
        if self._mapped_sources_list != source_list:
            self._mapped_sources = {
                cleanup_name_for_homekit(source): source for source in source_list
            }
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
        source = new_state.attributes.get(self.source_key)
        source_name = cleanup_name_for_homekit(source)
        _LOGGER.debug("%s: Set current input to %s", self.entity_id, source_name)
        if source_name in self.sources:
            index = self.sources.index(source_name)
            self.char_input_source.set_value(index)
            return

        possible_sources = self._get_ordered_source_list_from_state(new_state)
        if source_name in possible_sources:
            index = possible_sources.index(source_name)
            if index >= MAXIMUM_SOURCES:
                _LOGGER.debug(
                    "%s: Source %s and above are not supported",
                    self.entity_id,
                    MAXIMUM_SOURCES,
                )
            else:
                _LOGGER.debug(
                    "%s: Sources out of sync. Rebuilding Accessory",
                    self.entity_id,
                )
                return

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
            ATTR_CURRENT_ACTIVITY,
            ATTR_ACTIVITY_LIST,
            *args,
        )
        state = self.hass.states.get(self.entity_id)
        assert state
        self.async_update_state(state)

    def set_on_off(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s', self.entity_id, value)
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.async_call_service(REMOTE_DOMAIN, service, params)

    def set_input_source(self, value: int) -> None:
        """Send input set value if call came from HomeKit."""
        _LOGGER.debug("%s: Set current input to %s", self.entity_id, value)
        source = self._mapped_sources[self.sources[value]]
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_ACTIVITY: source}
        self.async_call_service(REMOTE_DOMAIN, SERVICE_TURN_ON, params)

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
    def async_update_state(self, new_state: State) -> None:
        """Update Television remote state after state changed."""
        current_state = new_state.state
        # Power state remote
        hk_state = 1 if current_state == STATE_ON else 0
        _LOGGER.debug("%s: Set current active state to %s", self.entity_id, hk_state)
        self.char_active.set_value(hk_state)

        self._async_update_input_state(hk_state, new_state)
