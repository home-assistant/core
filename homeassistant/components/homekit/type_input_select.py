"""Class for input selcet accessories."""
from abc import abstractmethod
import logging

from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import callback

from .accessories import HomeAccessory
from .const import (
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
    SERV_INPUT_SOURCE,
    SERV_TELEVISION,
)

_LOGGER = logging.getLogger(__name__)


class InputSelectAccessory(HomeAccessory):
    """Generate a InputSelect accessory."""

    def __init__(
        self,
        required_feature,
        source_key,
        source_list_key,
        *args,
        has_remote=False,
        **kwargs,
    ):
        """Initialize a InputSelect accessory object."""
        super().__init__(*args, **kwargs)
        state = self.hass.states.get(self.entity_id)
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        self.source_key = source_key
        self.sources = []
        self.support_select_source = False
        if features & required_feature:
            self.sources = state.attributes.get(source_list_key, [])
            if self.sources:
                self.support_select_source = True

        self.chars_tv = [CHAR_REMOTE_KEY] if has_remote else []
        serv_tv = self.serv_tv = self.add_preload_service(
            SERV_TELEVISION, self.chars_tv
        )
        if has_remote:
            self.char_remote_key = self.serv_tv.configure_char(
                CHAR_REMOTE_KEY, setter_callback=self.set_remote_key
            )
        self.set_primary_service(serv_tv)
        serv_tv.configure_char(CHAR_CONFIGURED_NAME, value=self.display_name)
        serv_tv.configure_char(CHAR_SLEEP_DISCOVER_MODE, value=True)
        self.char_active = serv_tv.configure_char(
            CHAR_ACTIVE, setter_callback=self.set_on_off
        )

        if self.support_select_source:
            self.char_input_source = serv_tv.configure_char(
                CHAR_ACTIVE_IDENTIFIER, setter_callback=self.set_input_source
            )
            for index, source in enumerate(self.sources):
                serv_input = self.add_preload_service(
                    SERV_INPUT_SOURCE, [CHAR_IDENTIFIER, CHAR_NAME]
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

    @abstractmethod
    def set_on_off(self, value):
        """Move switch state to value if call came from HomeKit."""

    @abstractmethod
    def set_input_source(self, value):
        """Send input set value if call came from HomeKit."""

    @callback
    def _async_update_input_state(self, hk_state, new_state):
        """Update input state after state changed."""
        # Set active input
        if not self.support_select_source or not self.sources:
            return
        source_name = new_state.attributes.get(self.source_key)
        _LOGGER.debug("%s: Set current input to %s", self.entity_id, source_name)
        if source_name in self.sources:
            index = self.sources.index(source_name)
            if self.char_input_source.value != index:
                self.char_input_source.set_value(index)
        elif hk_state:
            _LOGGER.warning(
                "%s: Sources out of sync. Restart Home Assistant",
                self.entity_id,
            )
            if self.char_input_source.value != 0:
                self.char_input_source.set_value(0)
