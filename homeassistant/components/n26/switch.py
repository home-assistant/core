"""Support for N26 switches."""
import logging

from homeassistant.components.switch import SwitchEntity

from . import DEFAULT_SCAN_INTERVAL, DOMAIN
from .const import CARD_STATE_ACTIVE, CARD_STATE_BLOCKED, DATA

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the N26 switch platform."""
    if discovery_info is None:
        return

    api_list = hass.data[DOMAIN][DATA]

    switch_entities = []
    for api_data in api_list:
        for card in api_data.cards:
            switch_entities.append(N26CardSwitch(api_data, card))

    add_entities(switch_entities)


class N26CardSwitch(SwitchEntity):
    """Representation of a N26 card block/unblock switch."""

    def __init__(self, api_data, card: dict):
        """Initialize the N26 card block/unblock switch."""
        self._data = api_data
        self._card = card

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._card["id"]

    @property
    def name(self) -> str:
        """Friendly name of the sensor."""
        return f"card_{self._card['id']}"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._card["status"] == CARD_STATE_ACTIVE

    def turn_on(self, **kwargs):
        """Block the card."""
        self._data.api.unblock_card(self._card["id"])
        self._card["status"] = CARD_STATE_ACTIVE

    def turn_off(self, **kwargs):
        """Unblock the card."""
        self._data.api.block_card(self._card["id"])
        self._card["status"] = CARD_STATE_BLOCKED

    def update(self):
        """Update the switch state."""
        self._data.update_cards()
        self._card = self._data.card(self._card["id"], self._card)
