"""Support for OwnTracks."""
from collections import defaultdict
import json
import logging
import re

from aiohttp.web import json_response
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_WEBHOOK_ID,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.setup import async_when_setup

from .config_flow import CONF_SECRET
from .const import DOMAIN
from .messages import async_handle_message, encrypt_message

_LOGGER = logging.getLogger(__name__)

CONF_MAX_GPS_ACCURACY = "max_gps_accuracy"
CONF_WAYPOINT_IMPORT = "waypoints"
CONF_WAYPOINT_WHITELIST = "waypoint_whitelist"
CONF_MQTT_TOPIC = "mqtt_topic"
CONF_REGION_MAPPING = "region_mapping"
CONF_EVENTS_ONLY = "events_only"
BEACON_DEV_ID = "beacon"

DEFAULT_OWNTRACKS_TOPIC = "owntracks/#"

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default={}): {
            vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
            vol.Optional(CONF_WAYPOINT_IMPORT, default=True): cv.boolean,
            vol.Optional(CONF_EVENTS_ONLY, default=False): cv.boolean,
            vol.Optional(
                CONF_MQTT_TOPIC, default=DEFAULT_OWNTRACKS_TOPIC
            ): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_WAYPOINT_WHITELIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_SECRET): vol.Any(
                vol.Schema({vol.Optional(cv.string): cv.string}), cv.string
            ),
            vol.Optional(CONF_REGION_MAPPING, default={}): dict,
            vol.Optional(CONF_WEBHOOK_ID): cv.string,
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Initialize OwnTracks component."""
    hass.data[DOMAIN] = {"config": config[DOMAIN], "devices": {}, "unsub": None}
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up OwnTracks entry."""
    config = hass.data[DOMAIN]["config"]
    max_gps_accuracy = config.get(CONF_MAX_GPS_ACCURACY)
    waypoint_import = config.get(CONF_WAYPOINT_IMPORT)
    waypoint_whitelist = config.get(CONF_WAYPOINT_WHITELIST)
    secret = config.get(CONF_SECRET) or entry.data[CONF_SECRET]
    region_mapping = config.get(CONF_REGION_MAPPING)
    events_only = config.get(CONF_EVENTS_ONLY)
    mqtt_topic = config.get(CONF_MQTT_TOPIC)

    context = OwnTracksContext(
        hass,
        secret,
        max_gps_accuracy,
        waypoint_import,
        waypoint_whitelist,
        region_mapping,
        events_only,
        mqtt_topic,
    )

    webhook_id = config.get(CONF_WEBHOOK_ID) or entry.data[CONF_WEBHOOK_ID]

    hass.data[DOMAIN]["context"] = context

    async_when_setup(hass, "mqtt", async_connect_mqtt)

    hass.components.webhook.async_register(
        DOMAIN, "OwnTracks", webhook_id, handle_webhook
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "device_tracker")
    )

    hass.data[DOMAIN]["unsub"] = hass.helpers.dispatcher.async_dispatcher_connect(
        DOMAIN, async_handle_message
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload an OwnTracks config entry."""
    hass.components.webhook.async_unregister(entry.data[CONF_WEBHOOK_ID])
    await hass.config_entries.async_forward_entry_unload(entry, "device_tracker")
    hass.data[DOMAIN]["unsub"]()

    return True


async def async_remove_entry(hass, entry):
    """Remove an OwnTracks config entry."""
    if not entry.data.get("cloudhook"):
        return

    await hass.components.cloud.async_delete_cloudhook(entry.data[CONF_WEBHOOK_ID])


async def async_connect_mqtt(hass, component):
    """Subscribe to MQTT topic."""
    context = hass.data[DOMAIN]["context"]

    async def async_handle_mqtt_message(msg):
        """Handle incoming OwnTracks message."""
        try:
            message = json.loads(msg.payload)
        except ValueError:
            # If invalid JSON
            _LOGGER.error("Unable to parse payload as JSON: %s", msg.payload)
            return

        message["topic"] = msg.topic
        hass.helpers.dispatcher.async_dispatcher_send(DOMAIN, hass, context, message)

    await hass.components.mqtt.async_subscribe(
        context.mqtt_topic, async_handle_mqtt_message, 1
    )

    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle webhook callback.

    iOS sets the "topic" as part of the payload.
    Android does not set a topic but adds headers to the request.
    """
    context = hass.data[DOMAIN]["context"]
    topic_base = re.sub("/#$", "", context.mqtt_topic)

    try:
        message = await request.json()
    except ValueError:
        _LOGGER.warning("Received invalid JSON from OwnTracks")
        return json_response([])

    # Android doesn't populate topic
    if "topic" not in message:
        headers = request.headers
        user = headers.get("X-Limit-U")
        device = headers.get("X-Limit-D", user)

        if user:
            message["topic"] = f"{topic_base}/{user}/{device}"

        elif message["_type"] != "encrypted":
            _LOGGER.warning(
                "No topic or user found in message. If on Android,"
                " set a username in Connection -> Identification"
            )
            # Keep it as a 200 response so the incorrect packet is discarded
            return json_response([])

    hass.helpers.dispatcher.async_dispatcher_send(DOMAIN, hass, context, message)

    response = []

    for person in hass.states.async_all("person"):
        if "latitude" in person.attributes and "longitude" in person.attributes:
            response.append(
                {
                    "_type": "location",
                    "lat": person.attributes["latitude"],
                    "lon": person.attributes["longitude"],
                    "tid": "".join(p[0] for p in person.name.split(" ")[:2]),
                    "tst": int(person.last_updated.timestamp()),
                }
            )

    if message["_type"] == "encrypted" and context.secret:
        return json_response(
            {
                "_type": "encrypted",
                "data": encrypt_message(
                    context.secret, message["topic"], json.dumps(response)
                ),
            }
        )

    return json_response(response)


class OwnTracksContext:
    """Hold the current OwnTracks context."""

    def __init__(
        self,
        hass,
        secret,
        max_gps_accuracy,
        import_waypoints,
        waypoint_whitelist,
        region_mapping,
        events_only,
        mqtt_topic,
    ):
        """Initialize an OwnTracks context."""
        self.hass = hass
        self.secret = secret
        self.max_gps_accuracy = max_gps_accuracy
        self.mobile_beacons_active = defaultdict(set)
        self.regions_entered = defaultdict(list)
        self.import_waypoints = import_waypoints
        self.waypoint_whitelist = waypoint_whitelist
        self.region_mapping = region_mapping
        self.events_only = events_only
        self.mqtt_topic = mqtt_topic
        self._pending_msg = []

    @callback
    def async_valid_accuracy(self, message):
        """Check if we should ignore this message."""
        acc = message.get("acc")

        if acc is None:
            return False

        try:
            acc = float(acc)
        except ValueError:
            return False

        if acc == 0:
            _LOGGER.warning(
                "Ignoring %s update because GPS accuracy is zero: %s",
                message["_type"],
                message,
            )
            return False

        if self.max_gps_accuracy is not None and acc > self.max_gps_accuracy:
            _LOGGER.info(
                "Ignoring %s update because expected GPS accuracy %s is not met: %s",
                message["_type"],
                self.max_gps_accuracy,
                message,
            )
            return False

        return True

    @callback
    def set_async_see(self, func):
        """Set a new async_see function."""
        self.async_see = func
        for msg in self._pending_msg:
            func(**msg)
        self._pending_msg.clear()

    # pylint: disable=method-hidden
    @callback
    def async_see(self, **data):
        """Send a see message to the device tracker."""
        self._pending_msg.append(data)

    @callback
    def async_see_beacons(self, hass, dev_id, kwargs_param):
        """Set active beacons to the current location."""
        kwargs = kwargs_param.copy()

        # Mobile beacons should always be set to the location of the
        # tracking device. I get the device state and make the necessary
        # changes to kwargs.
        device_tracker_state = hass.states.get(f"device_tracker.{dev_id}")

        if device_tracker_state is not None:
            acc = device_tracker_state.attributes.get(ATTR_GPS_ACCURACY)
            lat = device_tracker_state.attributes.get(ATTR_LATITUDE)
            lon = device_tracker_state.attributes.get(ATTR_LONGITUDE)

            if lat is not None and lon is not None:
                kwargs["gps"] = (lat, lon)
                kwargs["gps_accuracy"] = acc
            else:
                kwargs["gps"] = None
                kwargs["gps_accuracy"] = None

        # the battery state applies to the tracking device, not the beacon
        # kwargs location is the beacon's configured lat/lon
        kwargs.pop("battery", None)
        for beacon in self.mobile_beacons_active[dev_id]:
            kwargs["dev_id"] = f"{BEACON_DEV_ID}_{beacon}"
            kwargs["host_name"] = beacon
            self.async_see(**kwargs)
