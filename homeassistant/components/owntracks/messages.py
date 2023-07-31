"""OwnTracks Message handlers."""
import json
import logging

from nacl.encoding import Base64Encoder
from nacl.secret import SecretBox

from homeassistant.components import zone as zone_comp
from homeassistant.components.device_tracker import SourceType
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, STATE_HOME
from homeassistant.util import decorator, slugify

from .helper import supports_encryption

_LOGGER = logging.getLogger(__name__)

HANDLERS = decorator.Registry()  # type: ignore[var-annotated]


def get_cipher():
    """Return decryption function and length of key.

    Async friendly.
    """

    def decrypt(ciphertext, key):
        """Decrypt ciphertext using key."""
        return SecretBox(key).decrypt(ciphertext, encoder=Base64Encoder)

    return (SecretBox.KEY_SIZE, decrypt)


def _parse_topic(topic, subscribe_topic):
    """Parse an MQTT topic {sub_topic}/user/dev, return (user, dev) tuple.

    Async friendly.
    """
    subscription = subscribe_topic.split("/")
    try:
        user_index = subscription.index("#")
    except ValueError:
        _LOGGER.error("Can't parse subscription topic: '%s'", subscribe_topic)
        raise

    topic_list = topic.split("/")
    try:
        user, device = topic_list[user_index], topic_list[user_index + 1]
    except IndexError:
        _LOGGER.error("Can't parse topic: '%s'", topic)
        raise

    return user, device


def _parse_see_args(message, subscribe_topic):
    """Parse the OwnTracks location parameters, into the format see expects.

    Async friendly.
    """
    user, device = _parse_topic(message["topic"], subscribe_topic)
    dev_id = slugify(f"{user}_{device}")
    kwargs = {"dev_id": dev_id, "host_name": user, "attributes": {}}
    if message["lat"] is not None and message["lon"] is not None:
        kwargs["gps"] = (message["lat"], message["lon"])
    else:
        kwargs["gps"] = None

    if "acc" in message:
        kwargs["gps_accuracy"] = message["acc"]
    if "batt" in message:
        kwargs["battery"] = message["batt"]
    if "vel" in message:
        kwargs["attributes"]["velocity"] = message["vel"]
    if "tid" in message:
        kwargs["attributes"]["tid"] = message["tid"]
    if "addr" in message:
        kwargs["attributes"]["address"] = message["addr"]
    if "cog" in message:
        kwargs["attributes"]["course"] = message["cog"]
    if "bs" in message:
        kwargs["attributes"]["battery_status"] = message["bs"]
    if "t" in message:
        if message["t"] in ("c", "u"):
            kwargs["source_type"] = SourceType.GPS
        if message["t"] == "b":
            kwargs["source_type"] = SourceType.BLUETOOTH_LE

    return dev_id, kwargs


def _set_gps_from_zone(kwargs, location, zone):
    """Set the see parameters from the zone parameters.

    Async friendly.
    """
    if zone is not None:
        kwargs["gps"] = (
            zone.attributes[ATTR_LATITUDE],
            zone.attributes[ATTR_LONGITUDE],
        )
        kwargs["gps_accuracy"] = zone.attributes["radius"]
        kwargs["location_name"] = location
    return kwargs


def _decrypt_payload(secret, topic, ciphertext):
    """Decrypt encrypted payload."""
    try:
        if supports_encryption():
            keylen, decrypt = get_cipher()
        else:
            _LOGGER.warning("Ignoring encrypted payload because nacl not installed")
            return None
    except OSError:
        _LOGGER.warning("Ignoring encrypted payload because nacl not installed")
        return None

    if isinstance(secret, dict):
        key = secret.get(topic)
    else:
        key = secret

    if key is None:
        _LOGGER.warning(
            "Ignoring encrypted payload because no decryption key known for topic %s",
            topic,
        )
        return None

    key = key.encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b"\0")

    try:
        message = decrypt(ciphertext, key)
        message = message.decode("utf-8")
        _LOGGER.debug("Decrypted payload: %s", message)
        return message
    except ValueError:
        _LOGGER.warning(
            (
                "Ignoring encrypted payload because unable to decrypt using key for"
                " topic %s"
            ),
            topic,
        )
        return None


def encrypt_message(secret, topic, message):
    """Encrypt message."""

    keylen = SecretBox.KEY_SIZE

    if isinstance(secret, dict):
        key = secret.get(topic)
    else:
        key = secret

    if key is None:
        _LOGGER.warning(
            "Unable to encrypt payload because no decryption key known for topic %s",
            topic,
        )
        return None

    key = key.encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b"\0")

    try:
        message = message.encode("utf-8")
        payload = SecretBox(key).encrypt(message, encoder=Base64Encoder)
        _LOGGER.debug("Encrypted message: %s to %s", message, payload)
        return payload.decode("utf-8")
    except ValueError:
        _LOGGER.warning("Unable to encrypt message for topic %s", topic)
        return None


@HANDLERS.register("location")
async def async_handle_location_message(hass, context, message):
    """Handle a location message."""
    if not context.async_valid_accuracy(message):
        return

    if context.events_only:
        _LOGGER.debug("Location update ignored due to events_only setting")
        return

    dev_id, kwargs = _parse_see_args(message, context.mqtt_topic)

    if context.regions_entered[dev_id]:
        _LOGGER.debug(
            "Location update ignored, inside region %s", context.regions_entered[-1]
        )
        return

    context.async_see(**kwargs)
    context.async_see_beacons(hass, dev_id, kwargs)


async def _async_transition_message_enter(hass, context, message, location):
    """Execute enter event."""
    zone = hass.states.get(f"zone.{slugify(location)}")
    dev_id, kwargs = _parse_see_args(message, context.mqtt_topic)

    if zone is None and message.get("t") == "b":
        # Not a HA zone, and a beacon so mobile beacon.
        # kwargs will contain the lat/lon of the beacon
        # which is not where the beacon actually is
        # and is probably set to 0/0
        beacons = context.mobile_beacons_active[dev_id]
        if location not in beacons:
            beacons.add(location)
        _LOGGER.info("Added beacon %s", location)
        context.async_see_beacons(hass, dev_id, kwargs)
    else:
        # Normal region
        regions = context.regions_entered[dev_id]
        if location not in regions:
            regions.append(location)
        _LOGGER.info("Enter region %s", location)
        _set_gps_from_zone(kwargs, location, zone)
        context.async_see(**kwargs)
        context.async_see_beacons(hass, dev_id, kwargs)


async def _async_transition_message_leave(hass, context, message, location):
    """Execute leave event."""
    dev_id, kwargs = _parse_see_args(message, context.mqtt_topic)
    regions = context.regions_entered[dev_id]

    if location in regions:
        regions.remove(location)

    beacons = context.mobile_beacons_active[dev_id]
    if location in beacons:
        beacons.remove(location)
        _LOGGER.info("Remove beacon %s", location)
        context.async_see_beacons(hass, dev_id, kwargs)
    else:
        new_region = regions[-1] if regions else None
        if new_region:
            # Exit to previous region
            zone = hass.states.get(f"zone.{slugify(new_region)}")
            _set_gps_from_zone(kwargs, new_region, zone)
            _LOGGER.info("Exit to %s", new_region)
            context.async_see(**kwargs)
            context.async_see_beacons(hass, dev_id, kwargs)
            return

        _LOGGER.info("Exit to GPS")

        # Check for GPS accuracy
        if context.async_valid_accuracy(message):
            context.async_see(**kwargs)
            context.async_see_beacons(hass, dev_id, kwargs)


@HANDLERS.register("transition")
async def async_handle_transition_message(hass, context, message):
    """Handle a transition message."""
    if message.get("desc") is None:
        _LOGGER.error(
            "Location missing from `Entering/Leaving` message - "
            "please turn `Share` on in OwnTracks app"
        )
        return
    # OwnTracks uses - at the start of a beacon zone
    # to switch on 'hold mode' - ignore this
    location = message["desc"].lstrip("-")

    # Create a layer of indirection for Owntracks instances that may name
    # regions differently than their HA names
    if location in context.region_mapping:
        location = context.region_mapping[location]

    if location.lower() == "home":
        location = STATE_HOME

    if message["event"] == "enter":
        await _async_transition_message_enter(hass, context, message, location)
    elif message["event"] == "leave":
        await _async_transition_message_leave(hass, context, message, location)
    else:
        _LOGGER.error(
            "Misformatted mqtt msgs, _type=transition, event=%s", message["event"]
        )


async def async_handle_waypoint(hass, name_base, waypoint):
    """Handle a waypoint."""
    name = waypoint["desc"]
    pretty_name = f"{name_base} - {name}"
    lat = waypoint["lat"]
    lon = waypoint["lon"]
    rad = waypoint["rad"]

    # check zone exists
    entity_id = zone_comp.ENTITY_ID_FORMAT.format(slugify(pretty_name))

    # Check if state already exists
    if hass.states.get(entity_id) is not None:
        return

    zone = zone_comp.Zone.from_yaml(
        {
            zone_comp.CONF_NAME: pretty_name,
            zone_comp.CONF_LATITUDE: lat,
            zone_comp.CONF_LONGITUDE: lon,
            zone_comp.CONF_RADIUS: rad,
            zone_comp.CONF_ICON: zone_comp.ICON_IMPORT,
            zone_comp.CONF_PASSIVE: False,
        },
    )
    zone.hass = hass
    zone.entity_id = entity_id
    zone.async_write_ha_state()


@HANDLERS.register("waypoint")
@HANDLERS.register("waypoints")
async def async_handle_waypoints_message(hass, context, message):
    """Handle a waypoints message."""
    if not context.import_waypoints:
        return

    if context.waypoint_whitelist is not None:
        user = _parse_topic(message["topic"], context.mqtt_topic)[0]

        if user not in context.waypoint_whitelist:
            return

    wayps = message.get("waypoints", [message])

    _LOGGER.info("Got %d waypoints from %s", len(wayps), message["topic"])

    name_base = " ".join(_parse_topic(message["topic"], context.mqtt_topic))

    for wayp in wayps:
        await async_handle_waypoint(hass, name_base, wayp)


@HANDLERS.register("encrypted")
async def async_handle_encrypted_message(hass, context, message):
    """Handle an encrypted message."""
    if "topic" not in message and isinstance(context.secret, dict):
        _LOGGER.error("You cannot set per topic secrets when using HTTP")
        return

    plaintext_payload = _decrypt_payload(
        context.secret, message.get("topic"), message["data"]
    )

    if plaintext_payload is None:
        return

    decrypted = json.loads(plaintext_payload)
    if "topic" in message and "topic" not in decrypted:
        decrypted["topic"] = message["topic"]

    await async_handle_message(hass, context, decrypted)


@HANDLERS.register("lwt")
@HANDLERS.register("configuration")
@HANDLERS.register("beacon")
@HANDLERS.register("cmd")
@HANDLERS.register("steps")
@HANDLERS.register("card")
async def async_handle_not_impl_msg(hass, context, message):
    """Handle valid but not implemented message types."""
    _LOGGER.debug("Not handling %s message: %s", message.get("_type"), message)


async def async_handle_unsupported_msg(hass, context, message):
    """Handle an unsupported or invalid message type."""
    _LOGGER.warning("Received unsupported message type: %s", message.get("_type"))


async def async_handle_message(hass, context, message):
    """Handle an OwnTracks message."""
    msgtype = message.get("_type")

    _LOGGER.debug("Received %s", message)

    handler = HANDLERS.get(msgtype, async_handle_unsupported_msg)

    await handler(hass, context, message)
