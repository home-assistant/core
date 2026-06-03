"""Binary sensor support for Apple TV."""

from pyatv.const import FeatureName, FeatureState, KeyboardFocusState
from pyatv.interface import AppleTV, KeyboardListener

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SIGNAL_CONNECTED, AppleTvConfigEntry
from .entity import AppleTVEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AppleTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load Apple TV binary sensor based on a config entry."""
    manager = config_entry.runtime_data
    added = False

    @callback
    def setup_entities(atv: AppleTV) -> None:
        nonlocal added
        if added:
            return
        if atv.features.in_state(FeatureState.Available, FeatureName.TextFocusState):
            assert config_entry.unique_id is not None
            name: str = config_entry.data[CONF_NAME]
            async_add_entities(
                [AppleTVKeyboardFocused(name, config_entry.unique_id, manager)]
            )
            added = True

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_CONNECTED}_{config_entry.unique_id}", setup_entities
        )
    )

    # The manager may have already connected (and dispatched SIGNAL_CONNECTED)
    # before this platform was forwarded, in which case the signal above was
    # missed; handle that case directly.
    if manager.atv is not None:
        setup_entities(manager.atv)


class AppleTVKeyboardFocused(AppleTVEntity, BinarySensorEntity, KeyboardListener):
    """Binary sensor for Text input focused."""

    _attr_translation_key = "keyboard_focused"
    _attr_available = True

    @callback
    def async_device_connected(self, atv: AppleTV) -> None:
        """Handle when connection is made to device."""
        self._attr_available = True
        # Listen to keyboard updates
        atv.keyboard.listener = self
        # Set initial state based on current focus state
        self._update_state(atv.keyboard.text_focus_state is KeyboardFocusState.Focused)

    @callback
    def async_device_disconnected(self) -> None:
        """Handle when connection was lost to device."""
        self._attr_available = False
        self._update_state(False)

    def focusstate_update(
        self, old_state: KeyboardFocusState, new_state: KeyboardFocusState
    ) -> None:
        """Update keyboard state when it changes.

        This is a callback function from pyatv.interface.KeyboardListener.
        """
        self._update_state(new_state is KeyboardFocusState.Focused)

    def _update_state(self, new_state: bool) -> None:
        """Update and report."""
        self._attr_is_on = new_state
        self.async_write_ha_state()
