"""Adapter to wrap the rachiopy api for home assistant."""

import logging
from typing import Optional

from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from .const import (
    KEY_DEVICES,
    KEY_ENABLED,
    KEY_EXTERNAL_ID,
    KEY_ID,
    KEY_MAC_ADDRESS,
    KEY_MODEL,
    KEY_NAME,
    KEY_SERIAL_NUMBER,
    KEY_STATUS,
    KEY_USERNAME,
    KEY_ZONES,
)
from .webhooks import LISTEN_EVENT_TYPES, WEBHOOK_CONST_ID

_LOGGER = logging.getLogger(__name__)


class RachioPerson:
    """Represent a Rachio user."""

    def __init__(self, rachio, config_entry):
        """Create an object from the provided API instance."""
        # Use API token to get user ID
        self.rachio = rachio
        self.config_entry = config_entry
        self.username = None
        self._id = None
        self._controllers = []

    def setup(self, hass):
        """Rachio device setup."""
        response = self.rachio.person.getInfo()
        assert int(response[0][KEY_STATUS]) == 200, "API key error"
        self._id = response[1][KEY_ID]

        # Use user ID to get user data
        data = self.rachio.person.get(self._id)
        assert int(data[0][KEY_STATUS]) == 200, "User ID error"
        self.username = data[1][KEY_USERNAME]
        devices = data[1][KEY_DEVICES]
        for controller in devices:
            webhooks = self.rachio.notification.getDeviceWebhook(controller[KEY_ID])[1]
            # The API does not provide a way to tell if a controller is shared
            # or if they are the owner. To work around this problem we fetch the webooks
            # before we setup the device so we can skip it instead of failing.
            # webhooks are normally a list, however if there is an error
            # rachio hands us back a dict
            if isinstance(webhooks, dict):
                _LOGGER.error(
                    "Failed to add rachio controller '%s' because of an error: %s",
                    controller[KEY_NAME],
                    webhooks.get("error", "Unknown Error"),
                )
                continue

            rachio_iro = RachioIro(hass, self.rachio, controller, webhooks)
            rachio_iro.setup()
            self._controllers.append(rachio_iro)
        _LOGGER.info('Using Rachio API as user "%s"', self.username)

    @property
    def user_id(self) -> str:
        """Get the user ID as defined by the Rachio API."""
        return self._id

    @property
    def controllers(self) -> list:
        """Get a list of controllers managed by this account."""
        return self._controllers


class RachioIro:
    """Represent a Rachio Iro."""

    def __init__(self, hass, rachio, data, webhooks):
        """Initialize a Rachio device."""
        self.hass = hass
        self.rachio = rachio
        self._id = data[KEY_ID]
        self.name = data[KEY_NAME]
        self.serial_number = data[KEY_SERIAL_NUMBER]
        self.mac_address = data[KEY_MAC_ADDRESS]
        self.model = data[KEY_MODEL]
        self._zones = data[KEY_ZONES]
        self._init_data = data
        self._webhooks = webhooks
        _LOGGER.debug('%s has ID "%s"', str(self), self.controller_id)

    def setup(self):
        """Rachio Iro setup for webhooks."""
        # Listen for all updates
        self._init_webhooks()

    def _init_webhooks(self) -> None:
        """Start getting updates from the Rachio API."""
        current_webhook_id = None

        # First delete any old webhooks that may have stuck around
        def _deinit_webhooks(_) -> None:
            """Stop getting updates from the Rachio API."""
            if not self._webhooks:
                # We fetched webhooks when we created the device, however if we call _init_webhooks
                # again we need to fetch again
                self._webhooks = self.rachio.notification.getDeviceWebhook(
                    self.controller_id
                )[1]
            for webhook in self._webhooks:
                if (
                    webhook[KEY_EXTERNAL_ID].startswith(WEBHOOK_CONST_ID)
                    or webhook[KEY_ID] == current_webhook_id
                ):
                    self.rachio.notification.deleteWebhook(webhook[KEY_ID])
            self._webhooks = None

        _deinit_webhooks(None)

        # Choose which events to listen for and get their IDs
        event_types = []
        for event_type in self.rachio.notification.getWebhookEventType()[1]:
            if event_type[KEY_NAME] in LISTEN_EVENT_TYPES:
                event_types.append({"id": event_type[KEY_ID]})

        # Register to listen to these events from the device
        url = self.rachio.webhook_url
        auth = WEBHOOK_CONST_ID + self.rachio.webhook_auth
        new_webhook = self.rachio.notification.postWebhook(
            self.controller_id, auth, url, event_types
        )
        # Save ID for deletion at shutdown
        current_webhook_id = new_webhook[1][KEY_ID]
        self.hass.bus.listen(EVENT_HOMEASSISTANT_STOP, _deinit_webhooks)

    def __str__(self) -> str:
        """Display the controller as a string."""
        return f'Rachio controller "{self.name}"'

    @property
    def controller_id(self) -> str:
        """Return the Rachio API controller ID."""
        return self._id

    @property
    def current_schedule(self) -> str:
        """Return the schedule that the device is running right now."""
        return self.rachio.device.getCurrentSchedule(self.controller_id)[1]

    @property
    def init_data(self) -> dict:
        """Return the information used to set up the controller."""
        return self._init_data

    def list_zones(self, include_disabled=False) -> list:
        """Return a list of the zone dicts connected to the device."""
        # All zones
        if include_disabled:
            return self._zones

        # Only enabled zones
        return [z for z in self._zones if z[KEY_ENABLED]]

    def get_zone(self, zone_id) -> Optional[dict]:
        """Return the zone with the given ID."""
        for zone in self.list_zones(include_disabled=True):
            if zone[KEY_ID] == zone_id:
                return zone

        return None

    def stop_watering(self) -> None:
        """Stop watering all zones connected to this controller."""
        self.rachio.device.stopWater(self.controller_id)
        _LOGGER.info("Stopped watering of all zones on %s", str(self))
