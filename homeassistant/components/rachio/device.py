"""Adapter to wrap the rachiopy api for home assistant."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, HTTP_OK
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    KEY_DEVICES,
    KEY_ENABLED,
    KEY_EXTERNAL_ID,
    KEY_FLEX_SCHEDULES,
    KEY_ID,
    KEY_MAC_ADDRESS,
    KEY_MODEL,
    KEY_NAME,
    KEY_SCHEDULES,
    KEY_SERIAL_NUMBER,
    KEY_STATUS,
    KEY_USERNAME,
    KEY_ZONES,
    MODEL_GENERATION_1,
    SERVICE_PAUSE_WATERING,
    SERVICE_RESUME_WATERING,
    SERVICE_STOP_WATERING,
)
from .webhooks import LISTEN_EVENT_TYPES, WEBHOOK_CONST_ID

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICES = "devices"
ATTR_DURATION = "duration"
PERMISSION_ERROR = "7"

PAUSE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICES): cv.string,
        vol.Optional(ATTR_DURATION, default=60): cv.positive_int,
    }
)

RESUME_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICES): cv.string})

STOP_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICES): cv.string})


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

    async def async_setup(self, hass):
        """Create rachio devices and services."""
        await hass.async_add_executor_job(self._setup, hass)
        can_pause = False
        for rachio_iro in self._controllers:
            # Generation 1 controllers don't support pause or resume
            if rachio_iro.model.split("_")[0] != MODEL_GENERATION_1:
                can_pause = True
                break

        all_devices = [rachio_iro.name for rachio_iro in self._controllers]

        def pause_water(service):
            """Service to pause watering on all or specific controllers."""
            duration = service.data[ATTR_DURATION]
            devices = service.data.get(ATTR_DEVICES, all_devices)
            for iro in self._controllers:
                if iro.name in devices:
                    iro.pause_watering(duration)

        def resume_water(service):
            """Service to resume watering on all or specific controllers."""
            devices = service.data.get(ATTR_DEVICES, all_devices)
            for iro in self._controllers:
                if iro.name in devices:
                    iro.resume_watering()

        def stop_water(service):
            """Service to stop watering on all or specific controllers."""
            devices = service.data.get(ATTR_DEVICES, all_devices)
            for iro in self._controllers:
                if iro.name in devices:
                    iro.stop_watering()

        hass.services.async_register(
            DOMAIN,
            SERVICE_STOP_WATERING,
            stop_water,
            schema=STOP_SERVICE_SCHEMA,
        )

        if not can_pause:
            return

        hass.services.async_register(
            DOMAIN,
            SERVICE_PAUSE_WATERING,
            pause_water,
            schema=PAUSE_SERVICE_SCHEMA,
        )

        hass.services.async_register(
            DOMAIN,
            SERVICE_RESUME_WATERING,
            resume_water,
            schema=RESUME_SERVICE_SCHEMA,
        )

    def _setup(self, hass):
        """Rachio device setup."""
        rachio = self.rachio

        response = rachio.person.info()
        assert int(response[0][KEY_STATUS]) == HTTP_OK, "API key error"
        self._id = response[1][KEY_ID]

        # Use user ID to get user data
        data = rachio.person.get(self._id)
        assert int(data[0][KEY_STATUS]) == HTTP_OK, "User ID error"
        self.username = data[1][KEY_USERNAME]
        devices = data[1][KEY_DEVICES]
        for controller in devices:
            webhooks = rachio.notification.get_device_webhook(controller[KEY_ID])[1]
            # The API does not provide a way to tell if a controller is shared
            # or if they are the owner. To work around this problem we fetch the webhooks
            # before we setup the device so we can skip it instead of failing.
            # webhooks are normally a list, however if there is an error
            # rachio hands us back a dict
            if isinstance(webhooks, dict):
                if webhooks.get("code") == PERMISSION_ERROR:
                    _LOGGER.info(
                        "Not adding controller '%s', only controllers owned by '%s' may be added",
                        controller[KEY_NAME],
                        self.username,
                    )
                else:
                    _LOGGER.error(
                        "Failed to add rachio controller '%s' because of an error: %s",
                        controller[KEY_NAME],
                        webhooks.get("error", "Unknown Error"),
                    )
                continue

            rachio_iro = RachioIro(hass, rachio, controller, webhooks)
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

    def start_multiple_zones(self, zones) -> None:
        """Start multiple zones."""
        self.rachio.zone.start_multiple(zones)


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
        self._schedules = data[KEY_SCHEDULES]
        self._flex_schedules = data[KEY_FLEX_SCHEDULES]
        self._init_data = data
        self._webhooks = webhooks
        _LOGGER.debug('%s has ID "%s"', self, self.controller_id)

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
                self._webhooks = self.rachio.notification.get_device_webhook(
                    self.controller_id
                )[1]
            for webhook in self._webhooks:
                if (
                    webhook[KEY_EXTERNAL_ID].startswith(WEBHOOK_CONST_ID)
                    or webhook[KEY_ID] == current_webhook_id
                ):
                    self.rachio.notification.delete(webhook[KEY_ID])
            self._webhooks = None

        _deinit_webhooks(None)

        # Choose which events to listen for and get their IDs
        event_types = []
        for event_type in self.rachio.notification.get_webhook_event_type()[1]:
            if event_type[KEY_NAME] in LISTEN_EVENT_TYPES:
                event_types.append({"id": event_type[KEY_ID]})

        # Register to listen to these events from the device
        url = self.rachio.webhook_url
        auth = WEBHOOK_CONST_ID + self.rachio.webhook_auth
        new_webhook = self.rachio.notification.add(
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
        return self.rachio.device.current_schedule(self.controller_id)[1]

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

    def get_zone(self, zone_id) -> dict | None:
        """Return the zone with the given ID."""
        for zone in self.list_zones(include_disabled=True):
            if zone[KEY_ID] == zone_id:
                return zone

        return None

    def list_schedules(self) -> list:
        """Return a list of fixed schedules."""
        return self._schedules

    def list_flex_schedules(self) -> list:
        """Return a list of flex schedules."""
        return self._flex_schedules

    def stop_watering(self) -> None:
        """Stop watering all zones connected to this controller."""
        self.rachio.device.stop_water(self.controller_id)
        _LOGGER.info("Stopped watering of all zones on %s", self)

    def pause_watering(self, duration) -> None:
        """Pause watering on this controller."""
        self.rachio.device.pause_zone_run(self.controller_id, duration * 60)
        _LOGGER.debug("Paused watering on %s for %s minutes", self, duration)

    def resume_watering(self) -> None:
        """Resume paused watering on this controller."""
        self.rachio.device.resume_zone_run(self.controller_id)
        _LOGGER.debug("Resuming watering on %s", self)
