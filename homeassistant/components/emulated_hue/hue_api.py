"""Support for a Hue API to control Home Assistant."""
import asyncio
import hashlib
from ipaddress import ip_address
import logging
import time

from homeassistant import core
from homeassistant.components import (
    climate,
    cover,
    fan,
    humidifier,
    light,
    media_player,
    scene,
    script,
)
from homeassistant.components.climate.const import (
    SERVICE_SET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    SERVICE_SET_COVER_POSITION,
    SUPPORT_SET_POSITION,
)
from homeassistant.components.fan import (
    ATTR_SPEED,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.humidifier.const import (
    ATTR_HUMIDITY,
    SERVICE_SET_HUMIDITY,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
)
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_VOLUME_LEVEL,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
    HTTP_UNAUTHORIZED,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_SET,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.network import is_local

_LOGGER = logging.getLogger(__name__)

# How long to wait for a state change to happen
STATE_CHANGE_WAIT_TIMEOUT = 5.0
# How long an entry state's cache will be valid for in seconds.
STATE_CACHED_TIMEOUT = 2.0

STATE_BRIGHTNESS = "bri"
STATE_COLORMODE = "colormode"
STATE_HUE = "hue"
STATE_SATURATION = "sat"
STATE_COLOR_TEMP = "ct"
STATE_TRANSITON = "tt"
STATE_XY = "xy"

# Hue API states, defined separately in case they change
HUE_API_STATE_ON = "on"
HUE_API_STATE_BRI = "bri"
HUE_API_STATE_COLORMODE = "colormode"
HUE_API_STATE_HUE = "hue"
HUE_API_STATE_SAT = "sat"
HUE_API_STATE_CT = "ct"
HUE_API_STATE_XY = "xy"
HUE_API_STATE_EFFECT = "effect"
HUE_API_STATE_TRANSITION = "transitiontime"

# Hue API min/max values - https://developers.meethue.com/develop/hue-api/lights-api/
HUE_API_STATE_BRI_MIN = 1  # Brightness
HUE_API_STATE_BRI_MAX = 254
HUE_API_STATE_HUE_MIN = 0  # Hue
HUE_API_STATE_HUE_MAX = 65535
HUE_API_STATE_SAT_MIN = 0  # Saturation
HUE_API_STATE_SAT_MAX = 254
HUE_API_STATE_CT_MIN = 153  # Color temp
HUE_API_STATE_CT_MAX = 500

HUE_API_USERNAME = "nouser"
UNAUTHORIZED_USER = [
    {"error": {"address": "/", "description": "unauthorized user", "type": "1"}}
]


class HueUnauthorizedUser(HomeAssistantView):
    """Handle requests to find the emulated hue bridge."""

    url = "/api"
    name = "emulated_hue:api:unauthorized_user"
    extra_urls = ["/api/"]
    requires_auth = False

    async def get(self, request):
        """Handle a GET request."""
        return self.json(UNAUTHORIZED_USER)


class HueUsernameView(HomeAssistantView):
    """Handle requests to create a username for the emulated hue bridge."""

    url = "/api"
    name = "emulated_hue:api:create_username"
    extra_urls = ["/api/"]
    requires_auth = False

    async def post(self, request):
        """Handle a POST request."""
        if not is_local(ip_address(request.remote)):
            return self.json_message("Only local IPs allowed", HTTP_UNAUTHORIZED)

        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTP_BAD_REQUEST)

        if "devicetype" not in data:
            return self.json_message("devicetype not specified", HTTP_BAD_REQUEST)

        return self.json([{"success": {"username": HUE_API_USERNAME}}])


class HueAllGroupsStateView(HomeAssistantView):
    """Handle requests for getting info about entity groups."""

    url = "/api/{username}/groups"
    name = "emulated_hue:all_groups:state"
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request, username):
        """Process a request to make the Brilliant Lightpad work."""
        if not is_local(ip_address(request.remote)):
            return self.json_message("Only local IPs allowed", HTTP_UNAUTHORIZED)

        return self.json({})


class HueGroupView(HomeAssistantView):
    """Group handler to get Logitech Pop working."""

    url = "/api/{username}/groups/0/action"
    name = "emulated_hue:groups:state"
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def put(self, request, username):
        """Process a request to make the Logitech Pop working."""
        if not is_local(ip_address(request.remote)):
            return self.json_message("Only local IPs allowed", HTTP_UNAUTHORIZED)

        return self.json(
            [
                {
                    "error": {
                        "address": "/groups/0/action/scene",
                        "type": 7,
                        "description": "invalid value, dummy for parameter, scene",
                    }
                }
            ]
        )


class HueAllLightsStateView(HomeAssistantView):
    """Handle requests for getting info about all entities."""

    url = "/api/{username}/lights"
    name = "emulated_hue:lights:state"
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request, username):
        """Process a request to get the list of available lights."""
        if not is_local(ip_address(request.remote)):
            return self.json_message("Only local IPs allowed", HTTP_UNAUTHORIZED)

        return self.json(create_list_of_entities(self.config, request))


class HueFullStateView(HomeAssistantView):
    """Return full state view of emulated hue."""

    url = "/api/{username}"
    name = "emulated_hue:username:state"
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request, username):
        """Process a request to get the list of available lights."""
        if not is_local(ip_address(request.remote)):
            return self.json_message("only local IPs allowed", HTTP_UNAUTHORIZED)
        if username != HUE_API_USERNAME:
            return self.json(UNAUTHORIZED_USER)

        json_response = {
            "lights": create_list_of_entities(self.config, request),
            "config": create_config_model(self.config, request),
        }

        return self.json(json_response)


class HueConfigView(HomeAssistantView):
    """Return config view of emulated hue."""

    url = "/api/{username}/config"
    extra_urls = ["/api/config"]
    name = "emulated_hue:username:config"
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request, username=""):
        """Process a request to get the configuration."""
        if not is_local(ip_address(request.remote)):
            return self.json_message("only local IPs allowed", HTTP_UNAUTHORIZED)

        json_response = create_config_model(self.config, request)

        return self.json(json_response)


class HueOneLightStateView(HomeAssistantView):
    """Handle requests for getting info about a single entity."""

    url = "/api/{username}/lights/{entity_id}"
    name = "emulated_hue:light:state"
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request, username, entity_id):
        """Process a request to get the state of an individual light."""
        if not is_local(ip_address(request.remote)):
            return self.json_message("Only local IPs allowed", HTTP_UNAUTHORIZED)

        hass = request.app["hass"]
        hass_entity_id = self.config.number_to_entity_id(entity_id)

        if hass_entity_id is None:
            _LOGGER.error(
                "Unknown entity number: %s not found in emulated_hue_ids.json",
                entity_id,
            )
            return self.json_message("Entity not found", HTTP_NOT_FOUND)

        entity = hass.states.get(hass_entity_id)

        if entity is None:
            _LOGGER.error("Entity not found: %s", hass_entity_id)
            return self.json_message("Entity not found", HTTP_NOT_FOUND)

        if not self.config.is_entity_exposed(entity):
            _LOGGER.error("Entity not exposed: %s", entity_id)
            return self.json_message("Entity not exposed", HTTP_UNAUTHORIZED)

        json_response = entity_to_json(self.config, entity)

        return self.json(json_response)


class HueOneLightChangeView(HomeAssistantView):
    """Handle requests for setting info about entities."""

    url = "/api/{username}/lights/{entity_number}/state"
    name = "emulated_hue:light:state"
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    async def put(self, request, username, entity_number):
        """Process a request to set the state of an individual light."""
        if not is_local(ip_address(request.remote)):
            return self.json_message("Only local IPs allowed", HTTP_UNAUTHORIZED)

        config = self.config
        hass = request.app["hass"]
        entity_id = config.number_to_entity_id(entity_number)

        if entity_id is None:
            _LOGGER.error("Unknown entity number: %s", entity_number)
            return self.json_message("Entity not found", HTTP_NOT_FOUND)

        entity = hass.states.get(entity_id)

        if entity is None:
            _LOGGER.error("Entity not found: %s", entity_id)
            return self.json_message("Entity not found", HTTP_NOT_FOUND)

        if not config.is_entity_exposed(entity):
            _LOGGER.error("Entity not exposed: %s", entity_id)
            return self.json_message("Entity not exposed", HTTP_UNAUTHORIZED)

        try:
            request_json = await request.json()
        except ValueError:
            _LOGGER.error("Received invalid json")
            return self.json_message("Invalid JSON", HTTP_BAD_REQUEST)

        # Get the entity's supported features
        entity_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        # Parse the request
        parsed = {
            STATE_ON: False,
            STATE_BRIGHTNESS: None,
            STATE_HUE: None,
            STATE_SATURATION: None,
            STATE_COLOR_TEMP: None,
            STATE_XY: None,
            STATE_TRANSITON: None,
        }

        if HUE_API_STATE_ON in request_json:
            if not isinstance(request_json[HUE_API_STATE_ON], bool):
                _LOGGER.error("Unable to parse data: %s", request_json)
                return self.json_message("Bad request", HTTP_BAD_REQUEST)
            parsed[STATE_ON] = request_json[HUE_API_STATE_ON]
        else:
            parsed[STATE_ON] = entity.state != STATE_OFF

        for (key, attr) in (
            (HUE_API_STATE_BRI, STATE_BRIGHTNESS),
            (HUE_API_STATE_HUE, STATE_HUE),
            (HUE_API_STATE_SAT, STATE_SATURATION),
            (HUE_API_STATE_CT, STATE_COLOR_TEMP),
            (HUE_API_STATE_TRANSITION, STATE_TRANSITON),
        ):
            if key in request_json:
                try:
                    parsed[attr] = int(request_json[key])
                except ValueError:
                    _LOGGER.error("Unable to parse data (2): %s", request_json)
                    return self.json_message("Bad request", HTTP_BAD_REQUEST)
        if HUE_API_STATE_XY in request_json:
            try:
                parsed[STATE_XY] = (
                    float(request_json[HUE_API_STATE_XY][0]),
                    float(request_json[HUE_API_STATE_XY][1]),
                )
            except ValueError:
                _LOGGER.error("Unable to parse data (2): %s", request_json)
                return self.json_message("Bad request", HTTP_BAD_REQUEST)

        if HUE_API_STATE_BRI in request_json:
            if entity.domain == light.DOMAIN:
                if entity_features & SUPPORT_BRIGHTNESS:
                    parsed[STATE_ON] = parsed[STATE_BRIGHTNESS] > 0
                else:
                    parsed[STATE_BRIGHTNESS] = None

            elif entity.domain == scene.DOMAIN:
                parsed[STATE_BRIGHTNESS] = None
                parsed[STATE_ON] = True

            elif entity.domain in [
                script.DOMAIN,
                media_player.DOMAIN,
                fan.DOMAIN,
                cover.DOMAIN,
                climate.DOMAIN,
                humidifier.DOMAIN,
            ]:
                # Convert 0-254 to 0-100
                level = (parsed[STATE_BRIGHTNESS] / HUE_API_STATE_BRI_MAX) * 100
                parsed[STATE_BRIGHTNESS] = round(level)
                parsed[STATE_ON] = True

        # Choose general HA domain
        domain = core.DOMAIN

        # Entity needs separate call to turn on
        turn_on_needed = False

        # Convert the resulting "on" status into the service we need to call
        service = SERVICE_TURN_ON if parsed[STATE_ON] else SERVICE_TURN_OFF

        # Construct what we need to send to the service
        data = {ATTR_ENTITY_ID: entity_id}

        # If the requested entity is a light, set the brightness, hue,
        # saturation and color temp
        if entity.domain == light.DOMAIN:
            if parsed[STATE_ON]:
                if (
                    entity_features & SUPPORT_BRIGHTNESS
                    and parsed[STATE_BRIGHTNESS] is not None
                ):
                    data[ATTR_BRIGHTNESS] = hue_brightness_to_hass(
                        parsed[STATE_BRIGHTNESS]
                    )

                if entity_features & SUPPORT_COLOR:
                    if any((parsed[STATE_HUE], parsed[STATE_SATURATION])):
                        if parsed[STATE_HUE] is not None:
                            hue = parsed[STATE_HUE]
                        else:
                            hue = 0

                        if parsed[STATE_SATURATION] is not None:
                            sat = parsed[STATE_SATURATION]
                        else:
                            sat = 0

                        # Convert hs values to hass hs values
                        hue = int((hue / HUE_API_STATE_HUE_MAX) * 360)
                        sat = int((sat / HUE_API_STATE_SAT_MAX) * 100)

                        data[ATTR_HS_COLOR] = (hue, sat)

                    if parsed[STATE_XY] is not None:
                        data[ATTR_XY_COLOR] = parsed[STATE_XY]

                if (
                    entity_features & SUPPORT_COLOR_TEMP
                    and parsed[STATE_COLOR_TEMP] is not None
                ):
                    data[ATTR_COLOR_TEMP] = parsed[STATE_COLOR_TEMP]

                if (
                    entity_features & SUPPORT_TRANSITION
                    and parsed[STATE_TRANSITON] is not None
                ):
                    data[ATTR_TRANSITION] = parsed[STATE_TRANSITON] / 10

        # If the requested entity is a script, add some variables
        elif entity.domain == script.DOMAIN:
            data["variables"] = {
                "requested_state": STATE_ON if parsed[STATE_ON] else STATE_OFF
            }

            if parsed[STATE_BRIGHTNESS] is not None:
                data["variables"]["requested_level"] = parsed[STATE_BRIGHTNESS]

        # If the requested entity is a climate, set the temperature
        elif entity.domain == climate.DOMAIN:
            # We don't support turning climate devices on or off,
            # only setting the temperature
            service = None

            if (
                entity_features & SUPPORT_TARGET_TEMPERATURE
                and parsed[STATE_BRIGHTNESS] is not None
            ):
                domain = entity.domain
                service = SERVICE_SET_TEMPERATURE
                data[ATTR_TEMPERATURE] = parsed[STATE_BRIGHTNESS]

        # If the requested entity is a humidifier, set the humidity
        elif entity.domain == humidifier.DOMAIN:
            if parsed[STATE_BRIGHTNESS] is not None:
                turn_on_needed = True
                domain = entity.domain
                service = SERVICE_SET_HUMIDITY
                data[ATTR_HUMIDITY] = parsed[STATE_BRIGHTNESS]

        # If the requested entity is a media player, convert to volume
        elif entity.domain == media_player.DOMAIN:
            if (
                entity_features & SUPPORT_VOLUME_SET
                and parsed[STATE_BRIGHTNESS] is not None
            ):
                turn_on_needed = True
                domain = entity.domain
                service = SERVICE_VOLUME_SET
                # Convert 0-100 to 0.0-1.0
                data[ATTR_MEDIA_VOLUME_LEVEL] = parsed[STATE_BRIGHTNESS] / 100.0

        # If the requested entity is a cover, convert to open_cover/close_cover
        elif entity.domain == cover.DOMAIN:
            domain = entity.domain
            service = SERVICE_CLOSE_COVER
            if service == SERVICE_TURN_ON:
                service = SERVICE_OPEN_COVER

            if (
                entity_features & SUPPORT_SET_POSITION
                and parsed[STATE_BRIGHTNESS] is not None
            ):
                domain = entity.domain
                service = SERVICE_SET_COVER_POSITION
                data[ATTR_POSITION] = parsed[STATE_BRIGHTNESS]

        # If the requested entity is a fan, convert to speed
        elif (
            entity.domain == fan.DOMAIN
            and entity_features & SUPPORT_SET_SPEED
            and parsed[STATE_BRIGHTNESS] is not None
        ):
            domain = entity.domain
            # Convert 0-100 to a fan speed
            brightness = parsed[STATE_BRIGHTNESS]
            if brightness == 0:
                data[ATTR_SPEED] = SPEED_OFF
            elif 0 < brightness <= 33.3:
                data[ATTR_SPEED] = SPEED_LOW
            elif 33.3 < brightness <= 66.6:
                data[ATTR_SPEED] = SPEED_MEDIUM
            elif 66.6 < brightness <= 100:
                data[ATTR_SPEED] = SPEED_HIGH

        # Map the off command to on
        if entity.domain in config.off_maps_to_on_domains:
            service = SERVICE_TURN_ON

        # Separate call to turn on needed
        if turn_on_needed:
            hass.async_create_task(
                hass.services.async_call(
                    core.DOMAIN,
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: entity_id},
                    blocking=True,
                )
            )

        if service is not None:
            state_will_change = parsed[STATE_ON] != (entity.state != STATE_OFF)

            hass.async_create_task(
                hass.services.async_call(domain, service, data, blocking=True)
            )

            if state_will_change:
                # Wait for the state to change.
                await wait_for_state_change_or_timeout(
                    hass, entity_id, STATE_CACHED_TIMEOUT
                )

        # Create success responses for all received keys
        json_response = [
            create_hue_success_response(
                entity_number, HUE_API_STATE_ON, parsed[STATE_ON]
            )
        ]

        for (key, val) in (
            (STATE_BRIGHTNESS, HUE_API_STATE_BRI),
            (STATE_HUE, HUE_API_STATE_HUE),
            (STATE_SATURATION, HUE_API_STATE_SAT),
            (STATE_COLOR_TEMP, HUE_API_STATE_CT),
            (STATE_XY, HUE_API_STATE_XY),
            (STATE_TRANSITON, HUE_API_STATE_TRANSITION),
        ):
            if parsed[key] is not None:
                json_response.append(
                    create_hue_success_response(entity_number, val, parsed[key])
                )

        if entity.domain in config.off_maps_to_on_domains:
            # Caching is required because things like scripts and scenes won't
            # report as "off" to Alexa if an "off" command is received, because
            # they'll map to "on". Thus, instead of reporting its actual
            # status, we report what Alexa will want to see, which is the same
            # as the actual requested command.
            config.cached_states[entity_id] = [parsed, None]
        else:
            config.cached_states[entity_id] = [parsed, time.time()]

        return self.json(json_response)


def get_entity_state(config, entity):
    """Retrieve and convert state and brightness values for an entity."""
    cached_state_entry = config.cached_states.get(entity.entity_id, None)
    cached_state = None

    # Check if we have a cached entry, and if so if it hasn't expired.
    if cached_state_entry is not None:
        entry_state, entry_time = cached_state_entry
        if entry_time is None:
            # Handle the case where the entity is listed in config.off_maps_to_on_domains.
            cached_state = entry_state
        elif time.time() - entry_time < STATE_CACHED_TIMEOUT and entry_state[
            STATE_ON
        ] == (entity.state != STATE_OFF):
            # We only want to use the cache if the actual state of the entity
            # is in sync so that it can be detected as an error by Alexa.
            cached_state = entry_state
        else:
            # Remove the now stale cached entry.
            config.cached_states.pop(entity.entity_id)

    data = {
        STATE_ON: False,
        STATE_BRIGHTNESS: None,
        STATE_HUE: None,
        STATE_SATURATION: None,
        STATE_COLOR_TEMP: None,
    }

    if cached_state is None:
        data[STATE_ON] = entity.state != STATE_OFF

        if data[STATE_ON]:
            data[STATE_BRIGHTNESS] = hass_to_hue_brightness(
                entity.attributes.get(ATTR_BRIGHTNESS, 0)
            )
            hue_sat = entity.attributes.get(ATTR_HS_COLOR)
            if hue_sat is not None:
                hue = hue_sat[0]
                sat = hue_sat[1]
                # Convert hass hs values back to hue hs values
                data[STATE_HUE] = int((hue / 360.0) * HUE_API_STATE_HUE_MAX)
                data[STATE_SATURATION] = int((sat / 100.0) * HUE_API_STATE_SAT_MAX)
            else:
                data[STATE_HUE] = HUE_API_STATE_HUE_MIN
                data[STATE_SATURATION] = HUE_API_STATE_SAT_MIN
            data[STATE_COLOR_TEMP] = entity.attributes.get(ATTR_COLOR_TEMP, 0)

        else:
            data[STATE_BRIGHTNESS] = 0
            data[STATE_HUE] = 0
            data[STATE_SATURATION] = 0
            data[STATE_COLOR_TEMP] = 0

        # Get the entity's supported features
        entity_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if entity.domain == light.DOMAIN:
            if entity_features & SUPPORT_BRIGHTNESS:
                pass
        elif entity.domain == climate.DOMAIN:
            temperature = entity.attributes.get(ATTR_TEMPERATURE, 0)
            # Convert 0-100 to 0-254
            data[STATE_BRIGHTNESS] = round(temperature * HUE_API_STATE_BRI_MAX / 100)
        elif entity.domain == humidifier.DOMAIN:
            humidity = entity.attributes.get(ATTR_HUMIDITY, 0)
            # Convert 0-100 to 0-254
            data[STATE_BRIGHTNESS] = round(humidity * HUE_API_STATE_BRI_MAX / 100)
        elif entity.domain == media_player.DOMAIN:
            level = entity.attributes.get(
                ATTR_MEDIA_VOLUME_LEVEL, 1.0 if data[STATE_ON] else 0.0
            )
            # Convert 0.0-1.0 to 0-254
            data[STATE_BRIGHTNESS] = round(min(1.0, level) * HUE_API_STATE_BRI_MAX)
        elif entity.domain == fan.DOMAIN:
            speed = entity.attributes.get(ATTR_SPEED, 0)
            # Convert 0.0-1.0 to 0-254
            data[STATE_BRIGHTNESS] = 0
            if speed == SPEED_LOW:
                data[STATE_BRIGHTNESS] = 85
            elif speed == SPEED_MEDIUM:
                data[STATE_BRIGHTNESS] = 170
            elif speed == SPEED_HIGH:
                data[STATE_BRIGHTNESS] = HUE_API_STATE_BRI_MAX
        elif entity.domain == cover.DOMAIN:
            level = entity.attributes.get(ATTR_CURRENT_POSITION, 0)
            data[STATE_BRIGHTNESS] = round(level / 100 * HUE_API_STATE_BRI_MAX)
    else:
        data = cached_state
        # Make sure brightness is valid
        if data[STATE_BRIGHTNESS] is None:
            data[STATE_BRIGHTNESS] = HUE_API_STATE_BRI_MAX if data[STATE_ON] else 0

        # Make sure hue/saturation are valid
        if (data[STATE_HUE] is None) or (data[STATE_SATURATION] is None):
            data[STATE_HUE] = 0
            data[STATE_SATURATION] = 0

        # If the light is off, set the color to off
        if data[STATE_BRIGHTNESS] == 0:
            data[STATE_HUE] = 0
            data[STATE_SATURATION] = 0

    # Clamp brightness, hue, saturation, and color temp to valid values
    for (key, v_min, v_max) in (
        (STATE_BRIGHTNESS, HUE_API_STATE_BRI_MIN, HUE_API_STATE_BRI_MAX),
        (STATE_HUE, HUE_API_STATE_HUE_MIN, HUE_API_STATE_HUE_MAX),
        (STATE_SATURATION, HUE_API_STATE_SAT_MIN, HUE_API_STATE_SAT_MAX),
        (STATE_COLOR_TEMP, HUE_API_STATE_CT_MIN, HUE_API_STATE_CT_MAX),
    ):
        if data[key] is not None:
            data[key] = max(v_min, min(data[key], v_max))

    return data


def entity_to_json(config, entity):
    """Convert an entity to its Hue bridge JSON representation."""
    entity_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
    unique_id = hashlib.md5(entity.entity_id.encode()).hexdigest()
    unique_id = f"00:{unique_id[0:2]}:{unique_id[2:4]}:{unique_id[4:6]}:{unique_id[6:8]}:{unique_id[8:10]}:{unique_id[10:12]}:{unique_id[12:14]}-{unique_id[14:16]}"

    state = get_entity_state(config, entity)

    retval = {
        "state": {
            HUE_API_STATE_ON: state[STATE_ON],
            "reachable": entity.state != STATE_UNAVAILABLE,
            "mode": "homeautomation",
        },
        "name": config.get_entity_name(entity),
        "uniqueid": unique_id,
        "manufacturername": "Home Assistant",
        "swversion": "123",
    }

    if (
        (entity_features & SUPPORT_BRIGHTNESS)
        and (entity_features & SUPPORT_COLOR)
        and (entity_features & SUPPORT_COLOR_TEMP)
    ):
        # Extended Color light (Zigbee Device ID: 0x0210)
        # Same as Color light, but which supports additional setting of color temperature
        retval["type"] = "Extended color light"
        retval["modelid"] = "HASS231"
        retval["state"].update(
            {
                HUE_API_STATE_BRI: state[STATE_BRIGHTNESS],
                HUE_API_STATE_HUE: state[STATE_HUE],
                HUE_API_STATE_SAT: state[STATE_SATURATION],
                HUE_API_STATE_CT: state[STATE_COLOR_TEMP],
                HUE_API_STATE_EFFECT: "none",
            }
        )
        if state[STATE_HUE] > 0 or state[STATE_SATURATION] > 0:
            retval["state"][HUE_API_STATE_COLORMODE] = "hs"
        else:
            retval["state"][HUE_API_STATE_COLORMODE] = "ct"
    elif (entity_features & SUPPORT_BRIGHTNESS) and (entity_features & SUPPORT_COLOR):
        # Color light (Zigbee Device ID: 0x0200)
        # Supports on/off, dimming and color control (hue/saturation, enhanced hue, color loop and XY)
        retval["type"] = "Color light"
        retval["modelid"] = "HASS213"
        retval["state"].update(
            {
                HUE_API_STATE_BRI: state[STATE_BRIGHTNESS],
                HUE_API_STATE_COLORMODE: "hs",
                HUE_API_STATE_HUE: state[STATE_HUE],
                HUE_API_STATE_SAT: state[STATE_SATURATION],
                HUE_API_STATE_EFFECT: "none",
            }
        )
    elif (entity_features & SUPPORT_BRIGHTNESS) and (
        entity_features & SUPPORT_COLOR_TEMP
    ):
        # Color temperature light (Zigbee Device ID: 0x0220)
        # Supports groups, scenes, on/off, dimming, and setting of a color temperature
        retval["type"] = "Color temperature light"
        retval["modelid"] = "HASS312"
        retval["state"].update(
            {
                HUE_API_STATE_COLORMODE: "ct",
                HUE_API_STATE_CT: state[STATE_COLOR_TEMP],
                HUE_API_STATE_BRI: state[STATE_BRIGHTNESS],
            }
        )
    elif entity_features & (
        SUPPORT_BRIGHTNESS
        | SUPPORT_SET_POSITION
        | SUPPORT_SET_SPEED
        | SUPPORT_VOLUME_SET
        | SUPPORT_TARGET_TEMPERATURE
    ):
        # Dimmable light (Zigbee Device ID: 0x0100)
        # Supports groups, scenes, on/off and dimming
        retval["type"] = "Dimmable light"
        retval["modelid"] = "HASS123"
        retval["state"].update({HUE_API_STATE_BRI: state[STATE_BRIGHTNESS]})
    elif not config.lights_all_dimmable:
        # On/Off light (ZigBee Device ID: 0x0000)
        # Supports groups, scenes and on/off control
        retval["type"] = "On/Off light"
        retval["productname"] = "On/Off light"
        retval["modelid"] = "HASS321"
    else:
        # Dimmable light (Zigbee Device ID: 0x0100)
        # Supports groups, scenes, on/off and dimming
        # Reports fixed brightness for compatibility with Alexa.
        retval["type"] = "Dimmable light"
        retval["modelid"] = "HASS123"
        retval["state"].update({HUE_API_STATE_BRI: HUE_API_STATE_BRI_MAX})

    return retval


def create_hue_success_response(entity_number, attr, value):
    """Create a success response for an attribute set on a light."""
    success_key = f"/lights/{entity_number}/state/{attr}"
    return {"success": {success_key: value}}


def create_config_model(config, request):
    """Create a config resource."""
    return {
        "mac": "00:00:00:00:00:00",
        "swversion": "01003542",
        "apiversion": "1.17.0",
        "whitelist": {HUE_API_USERNAME: {"name": "HASS BRIDGE"}},
        "ipaddress": f"{config.advertise_ip}:{config.advertise_port}",
        "linkbutton": True,
    }


def create_list_of_entities(config, request):
    """Create a list of all entities."""
    hass = request.app["hass"]
    json_response = {}

    for entity in config.filter_exposed_entities(hass.states.async_all()):
        number = config.entity_id_to_number(entity.entity_id)
        json_response[number] = entity_to_json(config, entity)

    return json_response


def hue_brightness_to_hass(value):
    """Convert hue brightness 1..254 to hass format 0..255."""
    return min(255, round((value / HUE_API_STATE_BRI_MAX) * 255))


def hass_to_hue_brightness(value):
    """Convert hass brightness 0..255 to hue 1..254 scale."""
    return max(1, round((value / 255) * HUE_API_STATE_BRI_MAX))


async def wait_for_state_change_or_timeout(hass, entity_id, timeout):
    """Wait for an entity to change state."""
    ev = asyncio.Event()

    @core.callback
    def _async_event_changed(_):
        ev.set()

    unsub = async_track_state_change_event(hass, [entity_id], _async_event_changed)

    try:
        await asyncio.wait_for(ev.wait(), timeout=STATE_CHANGE_WAIT_TIMEOUT)
    except asyncio.TimeoutError:
        pass
    finally:
        unsub()
