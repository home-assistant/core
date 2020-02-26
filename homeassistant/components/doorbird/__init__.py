"""Support for DoorBird devices."""
import logging
from urllib.error import HTTPError

from doorbirdpy import DoorBird
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.logbook import log_entry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util, slugify

_LOGGER = logging.getLogger(__name__)

DOMAIN = "doorbird"

API_URL = f"/api/{DOMAIN}"

CONF_CUSTOM_URL = "hass_url_override"
CONF_EVENTS = "events"

RESET_DEVICE_FAVORITES = "doorbird_reset_favorites"

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_EVENTS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_CUSTOM_URL): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the DoorBird component."""

    # Provide an endpoint for the doorstations to call to trigger events
    hass.http.register_view(DoorBirdRequestView)

    doorstations = []

    for index, doorstation_config in enumerate(config[DOMAIN][CONF_DEVICES]):
        device_ip = doorstation_config.get(CONF_HOST)
        username = doorstation_config.get(CONF_USERNAME)
        password = doorstation_config.get(CONF_PASSWORD)
        custom_url = doorstation_config.get(CONF_CUSTOM_URL)
        events = doorstation_config.get(CONF_EVENTS)
        token = doorstation_config.get(CONF_TOKEN)
        name = doorstation_config.get(CONF_NAME) or f"DoorBird {index + 1}"

        try:
            device = DoorBird(device_ip, username, password)
            status = device.ready()
        except OSError as oserr:
            _LOGGER.error(
                "Failed to setup doorbird at %s: %s; not retrying", device_ip, oserr
            )
            continue

        if status[0]:
            doorstation = ConfiguredDoorBird(device, name, events, custom_url, token)
            doorstations.append(doorstation)
            _LOGGER.info(
                'Connected to DoorBird "%s" as %s@%s',
                doorstation.name,
                username,
                device_ip,
            )
        elif status[1] == 401:
            _LOGGER.error(
                "Authorization rejected by DoorBird for %s@%s", username, device_ip
            )
            return False
        else:
            _LOGGER.error(
                "Could not connect to DoorBird as %s@%s: Error %s",
                username,
                device_ip,
                str(status[1]),
            )
            return False

        # Subscribe to doorbell or motion events
        if events:
            try:
                doorstation.register_events(hass)
            except HTTPError:
                hass.components.persistent_notification.create(
                    "Doorbird configuration failed.  Please verify that API "
                    "Operator permission is enabled for the Doorbird user. "
                    "A restart will be required once permissions have been "
                    "verified.",
                    title="Doorbird Configuration Failure",
                    notification_id="doorbird_schedule_error",
                )

                return False

    hass.data[DOMAIN] = doorstations

    def _reset_device_favorites_handler(event):
        """Handle clearing favorites on device."""
        token = event.data.get("token")

        if token is None:
            return

        doorstation = get_doorstation_by_token(hass, token)

        if doorstation is None:
            _LOGGER.error("Device not found for provided token.")

        # Clear webhooks
        favorites = doorstation.device.favorites()

        for favorite_type in favorites:
            for favorite_id in favorites[favorite_type]:
                doorstation.device.delete_favorite(favorite_type, favorite_id)

    hass.bus.listen(RESET_DEVICE_FAVORITES, _reset_device_favorites_handler)

    return True


def get_doorstation_by_token(hass, token):
    """Get doorstation by slug."""
    for doorstation in hass.data[DOMAIN]:
        if token == doorstation.token:
            return doorstation


class ConfiguredDoorBird:
    """Attach additional information to pass along with configured device."""

    def __init__(self, device, name, events, custom_url, token):
        """Initialize configured device."""
        self._name = name
        self._device = device
        self._custom_url = custom_url
        self._events = events
        self._token = token

    @property
    def name(self):
        """Get custom device name."""
        return self._name

    @property
    def device(self):
        """Get the configured device."""
        return self._device

    @property
    def custom_url(self):
        """Get custom url for device."""
        return self._custom_url

    @property
    def token(self):
        """Get token for device."""
        return self._token

    def register_events(self, hass):
        """Register events on device."""
        # Get the URL of this server
        hass_url = hass.config.api.base_url

        # Override url if another is specified in the configuration
        if self.custom_url is not None:
            hass_url = self.custom_url

        for event in self._events:
            event = self._get_event_name(event)

            self._register_event(hass_url, event)

            _LOGGER.info("Successfully registered URL for %s on %s", event, self.name)

    @property
    def slug(self):
        """Get device slug."""
        return slugify(self._name)

    def _get_event_name(self, event):
        return f"{self.slug}_{event}"

    def _register_event(self, hass_url, event):
        """Add a schedule entry in the device for a sensor."""
        url = f"{hass_url}{API_URL}/{event}?token={self._token}"

        # Register HA URL as webhook if not already, then get the ID
        if not self.webhook_is_registered(url):
            self.device.change_favorite("http", f"Home Assistant ({event})", url)

        fav_id = self.get_webhook_id(url)

        if not fav_id:
            _LOGGER.warning(
                'Could not find favorite for URL "%s". ' 'Skipping sensor "%s"',
                url,
                event,
            )
            return

    def webhook_is_registered(self, url, favs=None) -> bool:
        """Return whether the given URL is registered as a device favorite."""
        favs = favs if favs else self.device.favorites()

        if "http" not in favs:
            return False

        for fav in favs["http"].values():
            if fav["value"] == url:
                return True

        return False

    def get_webhook_id(self, url, favs=None) -> str or None:
        """
        Return the device favorite ID for the given URL.

        The favorite must exist or there will be problems.
        """
        favs = favs if favs else self.device.favorites()

        if "http" not in favs:
            return None

        for fav_id in favs["http"]:
            if favs["http"][fav_id]["value"] == url:
                return fav_id

        return None

    def get_event_data(self):
        """Get data to pass along with HA event."""
        return {
            "timestamp": dt_util.utcnow().isoformat(),
            "live_video_url": self._device.live_video_url,
            "live_image_url": self._device.live_image_url,
            "rtsp_live_video_url": self._device.rtsp_live_video_url,
            "html5_viewer_url": self._device.html5_viewer_url,
        }


class DoorBirdRequestView(HomeAssistantView):
    """Provide a page for the device to call."""

    requires_auth = False
    url = API_URL
    name = API_URL[1:].replace("/", ":")
    extra_urls = [API_URL + "/{event}"]

    async def get(self, request, event):
        """Respond to requests from the device."""
        from aiohttp import web

        hass = request.app["hass"]

        token = request.query.get("token")

        device = get_doorstation_by_token(hass, token)

        if device is None:
            return web.Response(status=401, text="Invalid token provided.")

        if device:
            event_data = device.get_event_data()
        else:
            event_data = {}

        if event == "clear":
            hass.bus.async_fire(RESET_DEVICE_FAVORITES, {"token": token})

            message = f"HTTP Favorites cleared for {device.slug}"
            return web.Response(status=200, text=message)

        hass.bus.async_fire(f"{DOMAIN}_{event}", event_data)

        log_entry(hass, f"Doorbird {event}", "event was fired.", DOMAIN)

        return web.Response(status=200, text="OK")
