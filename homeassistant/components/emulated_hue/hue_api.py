"""Support for a Hue API to control Home Assistant."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from functools import lru_cache
import hashlib
from http import HTTPStatus
from ipaddress import ip_address
import logging
import time
from typing import Any

from aiohttp import web

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
from homeassistant.components.climate import (
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
)
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    CoverEntityFeature,
)
from homeassistant.components.fan import ATTR_PERCENTAGE, FanEntityFeature
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.humidifier import ATTR_HUMIDITY, SERVICE_SET_HUMIDITY
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_SET,
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, EventStateChangedData, State
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import color as color_util
from homeassistant.util.json import json_loads
from homeassistant.util.network import is_local

from .config import Config

_LOGGER = logging.getLogger(__name__)
_OFF_STATES: dict[str, str] = {cover.DOMAIN: STATE_CLOSED}

# How long to wait for a state change to happen
STATE_CHANGE_WAIT_TIMEOUT = 5.0
# How long an entry state's cache will be valid for in seconds.
STATE_CACHED_TIMEOUT = 2.0

STATE_BRIGHTNESS = "bri"
STATE_COLORMODE = "colormode"
STATE_HUE = "hue"
STATE_SATURATION = "sat"
STATE_COLOR_TEMP = "ct"
STATE_TRANSITION = "tt"
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

DIMMABLE_SUPPORTED_FEATURES_BY_DOMAIN = {
    cover.DOMAIN: CoverEntityFeature.SET_POSITION,
    fan.DOMAIN: FanEntityFeature.SET_SPEED,
    media_player.DOMAIN: MediaPlayerEntityFeature.VOLUME_SET,
    climate.DOMAIN: ClimateEntityFeature.TARGET_TEMPERATURE,
}

ENTITY_FEATURES_BY_DOMAIN = {
    cover.DOMAIN: CoverEntityFeature,
    fan.DOMAIN: FanEntityFeature,
    media_player.DOMAIN: MediaPlayerEntityFeature,
    climate.DOMAIN: ClimateEntityFeature,
}


@lru_cache(maxsize=32)
def _remote_is_allowed(address: str) -> bool:
    """Check if remote address is allowed."""
    return is_local(ip_address(address))


class HueUnauthorizedUser(HomeAssistantView):
    """Handle requests to find the emulated hue bridge."""

    url = "/api"
    name = "emulated_hue:api:unauthorized_user"
    extra_urls = ["/api/"]
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Handle a GET request."""
        return self.json(UNAUTHORIZED_USER)


class HueUsernameView(HomeAssistantView):
    """Handle requests to create a username for the emulated hue bridge."""

    url = "/api"
    name = "emulated_hue:api:create_username"
    extra_urls = ["/api/"]
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        """Handle a POST request."""
        assert request.remote is not None
        if not _remote_is_allowed(request.remote):
            return self.json_message("Only local IPs allowed", HTTPStatus.UNAUTHORIZED)

        try:
            data = await request.json(loads=json_loads)
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)

        if "devicetype" not in data:
            return self.json_message("devicetype not specified", HTTPStatus.BAD_REQUEST)

        return self.json([{"success": {"username": HUE_API_USERNAME}}])


class HueAllGroupsStateView(HomeAssistantView):
    """Handle requests for getting info about entity groups."""

    url = "/api/{username}/groups"
    name = "emulated_hue:all_groups:state"
    requires_auth = False

    def __init__(self, config: Config) -> None:
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request: web.Request, username: str) -> web.Response:
        """Process a request to make the Brilliant Lightpad work."""
        assert request.remote is not None
        if not _remote_is_allowed(request.remote):
            return self.json_message("Only local IPs allowed", HTTPStatus.UNAUTHORIZED)

        return self.json({})


class HueGroupView(HomeAssistantView):
    """Group handler to get Logitech Pop working."""

    url = "/api/{username}/groups/0/action"
    name = "emulated_hue:groups:state"
    requires_auth = False

    def __init__(self, config: Config) -> None:
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def put(self, request: web.Request, username: str) -> web.Response:
        """Process a request to make the Logitech Pop working."""
        assert request.remote is not None
        if not _remote_is_allowed(request.remote):
            return self.json_message("Only local IPs allowed", HTTPStatus.UNAUTHORIZED)

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

    def __init__(self, config: Config) -> None:
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request: web.Request, username: str) -> web.Response:
        """Process a request to get the list of available lights."""
        assert request.remote is not None
        if not _remote_is_allowed(request.remote):
            return self.json_message("Only local IPs allowed", HTTPStatus.UNAUTHORIZED)

        return self.json(create_list_of_entities(self.config, request))


class HueFullStateView(HomeAssistantView):
    """Return full state view of emulated hue."""

    url = "/api/{username}"
    name = "emulated_hue:username:state"
    requires_auth = False

    def __init__(self, config: Config) -> None:
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request: web.Request, username: str) -> web.Response:
        """Process a request to get the list of available lights."""
        assert request.remote is not None
        if not _remote_is_allowed(request.remote):
            return self.json_message("only local IPs allowed", HTTPStatus.UNAUTHORIZED)
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

    def __init__(self, config: Config) -> None:
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request: web.Request, username: str = "") -> web.Response:
        """Process a request to get the configuration."""
        assert request.remote is not None
        if not _remote_is_allowed(request.remote):
            return self.json_message("only local IPs allowed", HTTPStatus.UNAUTHORIZED)

        json_response = create_config_model(self.config, request)

        return self.json(json_response)


class HueOneLightStateView(HomeAssistantView):
    """Handle requests for getting info about a single entity."""

    url = "/api/{username}/lights/{entity_id}"
    name = "emulated_hue:light:state"
    requires_auth = False

    def __init__(self, config: Config) -> None:
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request: web.Request, username: str, entity_id: str) -> web.Response:
        """Process a request to get the state of an individual light."""
        assert request.remote is not None
        if not _remote_is_allowed(request.remote):
            return self.json_message("Only local IPs allowed", HTTPStatus.UNAUTHORIZED)

        hass = request.app[KEY_HASS]
        hass_entity_id = self.config.number_to_entity_id(entity_id)

        if hass_entity_id is None:
            _LOGGER.error(
                "Unknown entity number: %s not found in emulated_hue_ids.json",
                entity_id,
            )
            return self.json_message("Entity not found", HTTPStatus.NOT_FOUND)

        if (state := hass.states.get(hass_entity_id)) is None:
            _LOGGER.error("Entity not found: %s", hass_entity_id)
            return self.json_message("Entity not found", HTTPStatus.NOT_FOUND)

        if not self.config.is_state_exposed(state):
            _LOGGER.error("Entity not exposed: %s", entity_id)
            return self.json_message("Entity not exposed", HTTPStatus.UNAUTHORIZED)

        json_response = state_to_json(self.config, state)

        return self.json(json_response)


class HueOneLightChangeView(HomeAssistantView):
    """Handle requests for setting info about entities."""

    url = "/api/{username}/lights/{entity_number}/state"
    name = "emulated_hue:light:state"
    requires_auth = False

    def __init__(self, config: Config) -> None:
        """Initialize the instance of the view."""
        self.config = config

    async def put(  # noqa: C901
        self, request: web.Request, username: str, entity_number: str
    ) -> web.Response:
        """Process a request to set the state of an individual light."""
        assert request.remote is not None
        if not _remote_is_allowed(request.remote):
            return self.json_message("Only local IPs allowed", HTTPStatus.UNAUTHORIZED)

        config = self.config
        hass = request.app[KEY_HASS]
        entity_id = config.number_to_entity_id(entity_number)

        if entity_id is None:
            _LOGGER.error("Unknown entity number: %s", entity_number)
            return self.json_message("Entity not found", HTTPStatus.NOT_FOUND)

        if (entity := hass.states.get(entity_id)) is None:
            _LOGGER.error("Entity not found: %s", entity_id)
            return self.json_message("Entity not found", HTTPStatus.NOT_FOUND)

        if not config.is_state_exposed(entity):
            _LOGGER.error("Entity not exposed: %s", entity_id)
            return self.json_message("Entity not exposed", HTTPStatus.UNAUTHORIZED)

        try:
            request_json = await request.json()
        except ValueError:
            _LOGGER.error("Received invalid json")
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)

        # Get the entity's supported features
        entity_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if entity.domain == light.DOMAIN:
            color_modes = entity.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) or []

        # Parse the request
        parsed: dict[str, Any] = {
            STATE_ON: False,
            STATE_BRIGHTNESS: None,
            STATE_HUE: None,
            STATE_SATURATION: None,
            STATE_COLOR_TEMP: None,
            STATE_XY: None,
            STATE_TRANSITION: None,
        }

        if HUE_API_STATE_ON in request_json:
            if not isinstance(request_json[HUE_API_STATE_ON], bool):
                _LOGGER.error("Unable to parse data: %s", request_json)
                return self.json_message("Bad request", HTTPStatus.BAD_REQUEST)
            parsed[STATE_ON] = request_json[HUE_API_STATE_ON]
        else:
            parsed[STATE_ON] = _hass_to_hue_state(entity)

        for key, attr in (
            (HUE_API_STATE_BRI, STATE_BRIGHTNESS),
            (HUE_API_STATE_HUE, STATE_HUE),
            (HUE_API_STATE_SAT, STATE_SATURATION),
            (HUE_API_STATE_CT, STATE_COLOR_TEMP),
            (HUE_API_STATE_TRANSITION, STATE_TRANSITION),
        ):
            if key in request_json:
                try:
                    parsed[attr] = int(request_json[key])
                except ValueError:
                    _LOGGER.error("Unable to parse data (2): %s", request_json)
                    return self.json_message("Bad request", HTTPStatus.BAD_REQUEST)
        if HUE_API_STATE_XY in request_json:
            try:
                parsed[STATE_XY] = (
                    float(request_json[HUE_API_STATE_XY][0]),
                    float(request_json[HUE_API_STATE_XY][1]),
                )
            except ValueError:
                _LOGGER.error("Unable to parse data (2): %s", request_json)
                return self.json_message("Bad request", HTTPStatus.BAD_REQUEST)

        if HUE_API_STATE_BRI in request_json:
            if entity.domain == light.DOMAIN:
                if light.brightness_supported(color_modes):
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
        service: str | None = SERVICE_TURN_ON if parsed[STATE_ON] else SERVICE_TURN_OFF

        # Construct what we need to send to the service
        data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}

        # If the requested entity is a light, set the brightness, hue,
        # saturation and color temp
        if entity.domain == light.DOMAIN:
            if parsed[STATE_ON]:
                if (
                    light.brightness_supported(color_modes)
                    and parsed[STATE_BRIGHTNESS] is not None
                ):
                    data[ATTR_BRIGHTNESS] = hue_brightness_to_hass(
                        parsed[STATE_BRIGHTNESS]
                    )

                if light.color_supported(color_modes):
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
                    light.color_temp_supported(color_modes)
                    and parsed[STATE_COLOR_TEMP] is not None
                ):
                    data[ATTR_COLOR_TEMP_KELVIN] = (
                        color_util.color_temperature_mired_to_kelvin(
                            parsed[STATE_COLOR_TEMP]
                        )
                    )

                if (
                    entity_features & LightEntityFeature.TRANSITION
                    and parsed[STATE_TRANSITION] is not None
                ):
                    data[ATTR_TRANSITION] = parsed[STATE_TRANSITION] / 10

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
                entity_features & ClimateEntityFeature.TARGET_TEMPERATURE
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
                entity_features & MediaPlayerEntityFeature.VOLUME_SET
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
            if service == SERVICE_TURN_ON:
                service = SERVICE_OPEN_COVER
            else:
                service = SERVICE_CLOSE_COVER

            if (
                entity_features & CoverEntityFeature.SET_POSITION
                and parsed[STATE_BRIGHTNESS] is not None
            ):
                domain = entity.domain
                service = SERVICE_SET_COVER_POSITION
                data[ATTR_POSITION] = parsed[STATE_BRIGHTNESS]

        # If the requested entity is a fan, convert to speed
        elif (
            entity.domain == fan.DOMAIN
            and entity_features & FanEntityFeature.SET_SPEED
            and parsed[STATE_BRIGHTNESS] is not None
        ):
            domain = entity.domain
            # Convert 0-100 to a fan speed
            data[ATTR_PERCENTAGE] = parsed[STATE_BRIGHTNESS]

        # Map the off command to on
        if entity.domain in config.off_maps_to_on_domains:
            service = SERVICE_TURN_ON

        # Separate call to turn on needed
        if turn_on_needed:
            await hass.services.async_call(
                core.DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                blocking=False,
            )

        if service is not None:
            state_will_change = parsed[STATE_ON] != _hass_to_hue_state(entity)

            await hass.services.async_call(domain, service, data, blocking=False)

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

        for key, val in (
            (STATE_BRIGHTNESS, HUE_API_STATE_BRI),
            (STATE_HUE, HUE_API_STATE_HUE),
            (STATE_SATURATION, HUE_API_STATE_SAT),
            (STATE_COLOR_TEMP, HUE_API_STATE_CT),
            (STATE_XY, HUE_API_STATE_XY),
            (STATE_TRANSITION, HUE_API_STATE_TRANSITION),
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


def get_entity_state_dict(config: Config, entity: State) -> dict[str, Any]:
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
        ] == _hass_to_hue_state(entity):
            # We only want to use the cache if the actual state of the entity
            # is in sync so that it can be detected as an error by Alexa.
            cached_state = entry_state
        else:
            # Remove the now stale cached entry.
            config.cached_states.pop(entity.entity_id)

    if cached_state is None:
        return _build_entity_state_dict(entity)

    data: dict[str, Any] = cached_state
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

    _clamp_values(data)
    return data


@lru_cache(maxsize=512)
def _build_entity_state_dict(entity: State) -> dict[str, Any]:
    """Build a state dict for an entity."""
    is_on = _hass_to_hue_state(entity)
    data: dict[str, Any] = {
        STATE_ON: is_on,
        STATE_BRIGHTNESS: None,
        STATE_HUE: None,
        STATE_SATURATION: None,
        STATE_COLOR_TEMP: None,
    }
    attributes = entity.attributes
    if is_on:
        data[STATE_BRIGHTNESS] = hass_to_hue_brightness(
            attributes.get(ATTR_BRIGHTNESS) or 0
        )
        if (hue_sat := attributes.get(ATTR_HS_COLOR)) is not None:
            hue = hue_sat[0]
            sat = hue_sat[1]
            # Convert hass hs values back to hue hs values
            data[STATE_HUE] = int((hue / 360.0) * HUE_API_STATE_HUE_MAX)
            data[STATE_SATURATION] = int((sat / 100.0) * HUE_API_STATE_SAT_MAX)
        else:
            data[STATE_HUE] = HUE_API_STATE_HUE_MIN
            data[STATE_SATURATION] = HUE_API_STATE_SAT_MIN
        kelvin = attributes.get(ATTR_COLOR_TEMP_KELVIN)
        data[STATE_COLOR_TEMP] = (
            color_util.color_temperature_kelvin_to_mired(kelvin)
            if kelvin is not None
            else 0
        )

    else:
        data[STATE_BRIGHTNESS] = 0
        data[STATE_HUE] = 0
        data[STATE_SATURATION] = 0
        data[STATE_COLOR_TEMP] = 0

    if entity.domain == climate.DOMAIN:
        temperature = attributes.get(ATTR_TEMPERATURE, 0)
        # Convert 0-100 to 0-254
        data[STATE_BRIGHTNESS] = round(temperature * HUE_API_STATE_BRI_MAX / 100)
    elif entity.domain == humidifier.DOMAIN:
        humidity = attributes.get(ATTR_HUMIDITY, 0)
        # Convert 0-100 to 0-254
        data[STATE_BRIGHTNESS] = round(humidity * HUE_API_STATE_BRI_MAX / 100)
    elif entity.domain == media_player.DOMAIN:
        level = attributes.get(ATTR_MEDIA_VOLUME_LEVEL, 1.0 if is_on else 0.0)
        # Convert 0.0-1.0 to 0-254
        data[STATE_BRIGHTNESS] = round(min(1.0, level) * HUE_API_STATE_BRI_MAX)
    elif entity.domain == fan.DOMAIN:
        percentage = attributes.get(ATTR_PERCENTAGE) or 0
        # Convert 0-100 to 0-254
        data[STATE_BRIGHTNESS] = round(percentage * HUE_API_STATE_BRI_MAX / 100)
    elif entity.domain == cover.DOMAIN:
        level = attributes.get(ATTR_CURRENT_POSITION, 0)
        data[STATE_BRIGHTNESS] = round(level / 100 * HUE_API_STATE_BRI_MAX)
    _clamp_values(data)
    return data


def _clamp_values(data: dict[str, Any]) -> None:
    """Clamp brightness, hue, saturation, and color temp to valid values."""
    for key, v_min, v_max in (
        (STATE_BRIGHTNESS, HUE_API_STATE_BRI_MIN, HUE_API_STATE_BRI_MAX),
        (STATE_HUE, HUE_API_STATE_HUE_MIN, HUE_API_STATE_HUE_MAX),
        (STATE_SATURATION, HUE_API_STATE_SAT_MIN, HUE_API_STATE_SAT_MAX),
        (STATE_COLOR_TEMP, HUE_API_STATE_CT_MIN, HUE_API_STATE_CT_MAX),
    ):
        if data[key] is not None:
            data[key] = max(v_min, min(data[key], v_max))


@lru_cache(maxsize=1024)
def _entity_unique_id(entity_id: str) -> str:
    """Return the emulated_hue unique id for the entity_id."""
    unique_id = hashlib.md5(entity_id.encode()).hexdigest()
    return (
        f"00:{unique_id[0:2]}:{unique_id[2:4]}:"
        f"{unique_id[4:6]}:{unique_id[6:8]}:{unique_id[8:10]}:"
        f"{unique_id[10:12]}:{unique_id[12:14]}-{unique_id[14:16]}"
    )


def state_to_json(config: Config, state: State) -> dict[str, Any]:
    """Convert an entity to its Hue bridge JSON representation."""
    color_modes = state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) or []
    unique_id = _entity_unique_id(state.entity_id)
    state_dict = get_entity_state_dict(config, state)

    json_state: dict[str, str | bool | int] = {
        HUE_API_STATE_ON: state_dict[STATE_ON],
        "reachable": state.state != STATE_UNAVAILABLE,
        "mode": "homeautomation",
    }
    retval: dict[str, str | dict[str, str | bool | int]] = {
        "state": json_state,
        "name": config.get_entity_name(state),
        "uniqueid": unique_id,
        "manufacturername": "Home Assistant",
        "swversion": "123",
    }
    is_light = state.domain == light.DOMAIN
    color_supported = is_light and light.color_supported(color_modes)
    color_temp_supported = is_light and light.color_temp_supported(color_modes)
    if color_supported and color_temp_supported:
        # Extended Color light (Zigbee Device ID: 0x0210)
        # Same as Color light, but which supports additional setting of color temperature
        retval["type"] = "Extended color light"
        retval["modelid"] = "HASS231"
        json_state.update(
            {
                HUE_API_STATE_BRI: state_dict[STATE_BRIGHTNESS],
                HUE_API_STATE_HUE: state_dict[STATE_HUE],
                HUE_API_STATE_SAT: state_dict[STATE_SATURATION],
                HUE_API_STATE_CT: state_dict[STATE_COLOR_TEMP],
                HUE_API_STATE_EFFECT: "none",
            }
        )
        if state_dict[STATE_HUE] > 0 or state_dict[STATE_SATURATION] > 0:
            json_state[HUE_API_STATE_COLORMODE] = "hs"
        else:
            json_state[HUE_API_STATE_COLORMODE] = "ct"
    elif color_supported:
        # Color light (Zigbee Device ID: 0x0200)
        # Supports on/off, dimming and color control (hue/saturation, enhanced hue, color loop and XY)
        retval["type"] = "Color light"
        retval["modelid"] = "HASS213"
        json_state.update(
            {
                HUE_API_STATE_BRI: state_dict[STATE_BRIGHTNESS],
                HUE_API_STATE_COLORMODE: "hs",
                HUE_API_STATE_HUE: state_dict[STATE_HUE],
                HUE_API_STATE_SAT: state_dict[STATE_SATURATION],
                HUE_API_STATE_EFFECT: "none",
            }
        )
    elif color_temp_supported:
        # Color temperature light (Zigbee Device ID: 0x0220)
        # Supports groups, scenes, on/off, dimming, and setting of a color temperature
        retval["type"] = "Color temperature light"
        retval["modelid"] = "HASS312"
        json_state.update(
            {
                HUE_API_STATE_COLORMODE: "ct",
                HUE_API_STATE_CT: state_dict[STATE_COLOR_TEMP],
                HUE_API_STATE_BRI: state_dict[STATE_BRIGHTNESS],
            }
        )
    elif state_supports_hue_brightness(state, color_modes):
        # Dimmable light (Zigbee Device ID: 0x0100)
        # Supports groups, scenes, on/off and dimming
        retval["type"] = "Dimmable light"
        retval["modelid"] = "HASS123"
        json_state.update({HUE_API_STATE_BRI: state_dict[STATE_BRIGHTNESS]})
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
        json_state.update({HUE_API_STATE_BRI: HUE_API_STATE_BRI_MAX})

    return retval


def state_supports_hue_brightness(
    state: State, color_modes: Iterable[ColorMode]
) -> bool:
    """Return True if the state supports brightness."""
    domain = state.domain
    if domain == light.DOMAIN:
        return light.brightness_supported(color_modes)
    if not (required_feature := DIMMABLE_SUPPORTED_FEATURES_BY_DOMAIN.get(domain)):
        return False
    features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
    enum = ENTITY_FEATURES_BY_DOMAIN[domain]
    features = enum(features) if type(features) is int else features  # noqa: E721
    return required_feature in features


def create_hue_success_response(
    entity_number: str, attr: str, value: str
) -> dict[str, Any]:
    """Create a success response for an attribute set on a light."""
    success_key = f"/lights/{entity_number}/state/{attr}"
    return {"success": {success_key: value}}


def create_config_model(config: Config, request: web.Request) -> dict[str, Any]:
    """Create a config resource."""
    return {
        "name": "HASS BRIDGE",
        "mac": "00:00:00:00:00:00",
        "swversion": "01003542",
        "apiversion": "1.17.0",
        "whitelist": {HUE_API_USERNAME: {"name": "HASS BRIDGE"}},
        "ipaddress": f"{config.advertise_ip}:{config.advertise_port}",
        "linkbutton": True,
    }


def create_list_of_entities(config: Config, request: web.Request) -> dict[str, Any]:
    """Create a list of all entities."""
    hass = request.app[KEY_HASS]
    return {
        config.entity_id_to_number(entity_id): state_to_json(config, state)
        for entity_id in config.get_exposed_entity_ids()
        if (state := hass.states.get(entity_id))
    }


def hue_brightness_to_hass(value: int) -> int:
    """Convert hue brightness 1..254 to hass format 0..255."""
    return min(255, round((value / HUE_API_STATE_BRI_MAX) * 255))


def hass_to_hue_brightness(value: int) -> int:
    """Convert hass brightness 0..255 to hue 1..254 scale."""
    return max(1, round((value / 255) * HUE_API_STATE_BRI_MAX))


def _hass_to_hue_state(entity: State) -> bool:
    """Convert hass entity states to simple True/False on/off state for Hue."""
    return entity.state != _OFF_STATES.get(entity.domain, STATE_OFF)


async def wait_for_state_change_or_timeout(
    hass: core.HomeAssistant, entity_id: str, timeout: float
) -> None:
    """Wait for an entity to change state."""
    ev = asyncio.Event()

    @core.callback
    def _async_event_changed(event: Event[EventStateChangedData]) -> None:
        ev.set()

    unsub = async_track_state_change_event(hass, [entity_id], _async_event_changed)

    try:
        async with asyncio.timeout(STATE_CHANGE_WAIT_TIMEOUT):
            await ev.wait()
    except TimeoutError:
        pass
    finally:
        unsub()
