"""Support for setting the Transmission BitTorrent client Turtle Mode."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGING = logging.getLogger(__name__)

ENTITY_DESCRIPTIONS = [
    SwitchEntityDescription(
        key="on_off",
        name="Switch",
    ),
    SwitchEntityDescription(
        key="turtle_mode",
        name="Turtle mode",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission switch."""

    tm_client = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    dev = [
        TransmissionSwitch(entity_description, tm_client, name)
        for entity_description in ENTITY_DESCRIPTIONS
    ]

    async_add_entities(dev, True)


class TransmissionSwitch(SwitchEntity):
    """Representation of a Transmission switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entity_description, tm_client, client_name):
        """Initialize the Transmission switch."""
        self.entity_description = entity_description
        self._tm_client = tm_client
        self._state = STATE_OFF
        self._data = None
        self.unsub_update = None

        self._attr_unique_id = (
            f"{tm_client.config_entry.entry_id}-{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tm_client.config_entry.entry_id)},
            manufacturer="Transmission",
            name=client_name,
        )

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._tm_client.api.available

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self.entity_description.key == "on_off":
            _LOGGING.debug("Starting all torrents")
            self._tm_client.api.start_torrents()
        elif self.entity_description.key == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission on")
            self._tm_client.api.set_alt_speed_enabled(True)
        self._tm_client.api.update()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self.entity_description.key == "on_off":
            _LOGGING.debug("Stopping all torrents")
            self._tm_client.api.stop_torrents()
        if self.entity_description.key == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission off")
            self._tm_client.api.set_alt_speed_enabled(False)
        self._tm_client.api.update()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.unsub_update = async_dispatcher_connect(
            self.hass,
            self._tm_client.api.signal_update,
            self._schedule_immediate_update,
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    async def will_remove_from_hass(self):
        """Unsubscribe from update dispatcher."""
        if self.unsub_update:
            self.unsub_update()
            self.unsub_update = None

    def update(self) -> None:
        """Get the latest data from Transmission and updates the state."""
        active = None
        if self.entity_description.key == "on_off":
            self._data = self._tm_client.api.data
            if self._data:
                active = self._data.activeTorrentCount > 0

        elif self.entity_description.key == "turtle_mode":
            active = self._tm_client.api.get_alt_speed_enabled()

        if active is None:
            return

        self._state = STATE_ON if active else STATE_OFF
