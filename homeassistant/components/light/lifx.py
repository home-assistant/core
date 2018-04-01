"""
Support for the LIFX platform that implements lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.lifx/
"""
import asyncio
from datetime import timedelta
from functools import partial
import logging
import math
import sys

import voluptuous as vol

from homeassistant import util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_BRIGHTNESS_PCT, ATTR_COLOR_NAME, ATTR_COLOR_TEMP,
    ATTR_EFFECT, ATTR_HS_COLOR, ATTR_KELVIN, ATTR_RGB_COLOR, ATTR_TRANSITION,
    ATTR_XY_COLOR, COLOR_GROUP, DOMAIN, LIGHT_TURN_ON_SCHEMA, PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT,
    SUPPORT_TRANSITION, VALID_BRIGHTNESS, VALID_BRIGHTNESS_PCT, Light,
    preprocess_turn_on_alternatives)
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.service import extract_entity_ids
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['aiolifx==0.6.1', 'aiolifx_effects==0.1.2']

UDP_BROADCAST_PORT = 56700

DISCOVERY_INTERVAL = 60
MESSAGE_TIMEOUT = 1.0
MESSAGE_RETRIES = 8
UNAVAILABLE_GRACE = 90

CONF_SERVER = 'server'
CONF_BROADCAST = 'broadcast'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SERVER, default='0.0.0.0'): cv.string,
    vol.Optional(CONF_BROADCAST, default='255.255.255.255'): cv.string,
})

SERVICE_LIFX_SET_STATE = 'lifx_set_state'

ATTR_INFRARED = 'infrared'
ATTR_ZONES = 'zones'
ATTR_POWER = 'power'

LIFX_SET_STATE_SCHEMA = LIGHT_TURN_ON_SCHEMA.extend({
    ATTR_INFRARED: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
    ATTR_ZONES: vol.All(cv.ensure_list, [cv.positive_int]),
    ATTR_POWER: cv.boolean,
})

SERVICE_EFFECT_PULSE = 'lifx_effect_pulse'
SERVICE_EFFECT_COLORLOOP = 'lifx_effect_colorloop'
SERVICE_EFFECT_STOP = 'lifx_effect_stop'

ATTR_POWER_ON = 'power_on'
ATTR_MODE = 'mode'
ATTR_PERIOD = 'period'
ATTR_CYCLES = 'cycles'
ATTR_SPREAD = 'spread'
ATTR_CHANGE = 'change'

PULSE_MODE_BLINK = 'blink'
PULSE_MODE_BREATHE = 'breathe'
PULSE_MODE_PING = 'ping'
PULSE_MODE_STROBE = 'strobe'
PULSE_MODE_SOLID = 'solid'

PULSE_MODES = [PULSE_MODE_BLINK, PULSE_MODE_BREATHE, PULSE_MODE_PING,
               PULSE_MODE_STROBE, PULSE_MODE_SOLID]

LIFX_EFFECT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_POWER_ON, default=True): cv.boolean,
})

LIFX_EFFECT_PULSE_SCHEMA = LIFX_EFFECT_SCHEMA.extend({
    ATTR_BRIGHTNESS: VALID_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT: VALID_BRIGHTNESS_PCT,
    vol.Exclusive(ATTR_COLOR_NAME, COLOR_GROUP): cv.string,
    vol.Exclusive(ATTR_RGB_COLOR, COLOR_GROUP):
        vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)),
                vol.Coerce(tuple)),
    vol.Exclusive(ATTR_XY_COLOR, COLOR_GROUP):
        vol.All(vol.ExactSequence((cv.small_float, cv.small_float)),
                vol.Coerce(tuple)),
    vol.Exclusive(ATTR_HS_COLOR, COLOR_GROUP):
        vol.All(vol.ExactSequence(
            (vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
             vol.All(vol.Coerce(float), vol.Range(min=0, max=100)))),
                vol.Coerce(tuple)),
    vol.Exclusive(ATTR_COLOR_TEMP, COLOR_GROUP):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Exclusive(ATTR_KELVIN, COLOR_GROUP):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
    ATTR_PERIOD: vol.All(vol.Coerce(float), vol.Range(min=0.05)),
    ATTR_CYCLES: vol.All(vol.Coerce(float), vol.Range(min=1)),
    ATTR_MODE: vol.In(PULSE_MODES),
})

LIFX_EFFECT_COLORLOOP_SCHEMA = LIFX_EFFECT_SCHEMA.extend({
    ATTR_BRIGHTNESS: VALID_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT: VALID_BRIGHTNESS_PCT,
    ATTR_PERIOD: vol.All(vol.Coerce(float), vol.Clamp(min=0.05)),
    ATTR_CHANGE: vol.All(vol.Coerce(float), vol.Clamp(min=0, max=360)),
    ATTR_SPREAD: vol.All(vol.Coerce(float), vol.Clamp(min=0, max=360)),
    ATTR_TRANSITION: vol.All(vol.Coerce(float), vol.Range(min=0)),
})

LIFX_EFFECT_STOP_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def aiolifx():
    """Return the aiolifx module."""
    import aiolifx as aiolifx_module
    return aiolifx_module


def aiolifx_effects():
    """Return the aiolifx_effects module."""
    import aiolifx_effects as aiolifx_effects_module
    return aiolifx_effects_module


async def async_setup_platform(hass,
                               config,
                               async_add_devices,
                               discovery_info=None):
    """Set up the LIFX platform."""
    if sys.platform == 'win32':
        _LOGGER.warning("The lifx platform is known to not work on Windows. "
                        "Consider using the lifx_legacy platform instead")

    server_addr = config.get(CONF_SERVER)

    lifx_manager = LIFXManager(hass, async_add_devices)
    lifx_discovery = aiolifx().LifxDiscovery(
        hass.loop,
        lifx_manager,
        discovery_interval=DISCOVERY_INTERVAL,
        broadcast_ip=config.get(CONF_BROADCAST))

    coro = hass.loop.create_datagram_endpoint(
        lambda: lifx_discovery, local_addr=(server_addr, UDP_BROADCAST_PORT))

    hass.async_add_job(coro)

    @callback
    def cleanup(event):
        """Clean up resources."""
        lifx_discovery.cleanup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    return True


def lifx_features(device):
    """Return a feature map for this device, or a default map if unknown."""
    return aiolifx().products.features_map.get(device.product) or \
        aiolifx().products.features_map.get(1)


def find_hsbk(**kwargs):
    """Find the desired color from a number of possible inputs."""
    hue, saturation, brightness, kelvin = [None]*4

    preprocess_turn_on_alternatives(kwargs)

    if ATTR_HS_COLOR in kwargs:
        hue, saturation = kwargs[ATTR_HS_COLOR]
        hue = int(hue / 360 * 65535)
        saturation = int(saturation / 100 * 65535)
        kelvin = 3500

    if ATTR_COLOR_TEMP in kwargs:
        kelvin = int(color_util.color_temperature_mired_to_kelvin(
            kwargs[ATTR_COLOR_TEMP]))
        saturation = 0

    if ATTR_BRIGHTNESS in kwargs:
        brightness = convert_8_to_16(kwargs[ATTR_BRIGHTNESS])

    hsbk = [hue, saturation, brightness, kelvin]
    return None if hsbk == [None]*4 else hsbk


def merge_hsbk(base, change):
    """Copy change on top of base, except when None."""
    if change is None:
        return None
    return list(map(lambda x, y: y if y is not None else x, base, change))


class LIFXManager(object):
    """Representation of all known LIFX entities."""

    def __init__(self, hass, async_add_devices):
        """Initialize the light."""
        self.entities = {}
        self.hass = hass
        self.async_add_devices = async_add_devices
        self.effects_conductor = aiolifx_effects().Conductor(loop=hass.loop)

        self.register_set_state()
        self.register_effects()

    def register_set_state(self):
        """Register the LIFX set_state service call."""
        async def service_handler(service):
            """Apply a service."""
            tasks = []
            for light in self.service_to_entities(service):
                if service.service == SERVICE_LIFX_SET_STATE:
                    task = light.set_state(**service.data)
                tasks.append(self.hass.async_add_job(task))
            if tasks:
                await asyncio.wait(tasks, loop=self.hass.loop)

        self.hass.services.async_register(
            DOMAIN, SERVICE_LIFX_SET_STATE, service_handler,
            schema=LIFX_SET_STATE_SCHEMA)

    def register_effects(self):
        """Register the LIFX effects as hass service calls."""
        async def service_handler(service):
            """Apply a service, i.e. start an effect."""
            entities = self.service_to_entities(service)
            if entities:
                await self.start_effect(
                    entities, service.service, **service.data)

        self.hass.services.async_register(
            DOMAIN, SERVICE_EFFECT_PULSE, service_handler,
            schema=LIFX_EFFECT_PULSE_SCHEMA)

        self.hass.services.async_register(
            DOMAIN, SERVICE_EFFECT_COLORLOOP, service_handler,
            schema=LIFX_EFFECT_COLORLOOP_SCHEMA)

        self.hass.services.async_register(
            DOMAIN, SERVICE_EFFECT_STOP, service_handler,
            schema=LIFX_EFFECT_STOP_SCHEMA)

    async def start_effect(self, entities, service, **kwargs):
        """Start a light effect on entities."""
        devices = list(map(lambda l: l.device, entities))

        if service == SERVICE_EFFECT_PULSE:
            effect = aiolifx_effects().EffectPulse(
                power_on=kwargs.get(ATTR_POWER_ON),
                period=kwargs.get(ATTR_PERIOD),
                cycles=kwargs.get(ATTR_CYCLES),
                mode=kwargs.get(ATTR_MODE),
                hsbk=find_hsbk(**kwargs),
            )
            await self.effects_conductor.start(effect, devices)
        elif service == SERVICE_EFFECT_COLORLOOP:
            preprocess_turn_on_alternatives(kwargs)

            brightness = None
            if ATTR_BRIGHTNESS in kwargs:
                brightness = convert_8_to_16(kwargs[ATTR_BRIGHTNESS])

            effect = aiolifx_effects().EffectColorloop(
                power_on=kwargs.get(ATTR_POWER_ON),
                period=kwargs.get(ATTR_PERIOD),
                change=kwargs.get(ATTR_CHANGE),
                spread=kwargs.get(ATTR_SPREAD),
                transition=kwargs.get(ATTR_TRANSITION),
                brightness=brightness,
            )
            await self.effects_conductor.start(effect, devices)
        elif service == SERVICE_EFFECT_STOP:
            await self.effects_conductor.stop(devices)

    def service_to_entities(self, service):
        """Return the known devices that a service call mentions."""
        entity_ids = extract_entity_ids(self.hass, service)
        if entity_ids:
            entities = [entity for entity in self.entities.values()
                        if entity.entity_id in entity_ids]
        else:
            entities = list(self.entities.values())

        return entities

    @callback
    def register(self, device):
        """Handle aiolifx detected bulb."""
        self.hass.async_add_job(self.register_new_device(device))

    async def register_new_device(self, device):
        """Handle newly detected bulb."""
        if device.mac_addr in self.entities:
            entity = self.entities[device.mac_addr]
            entity.registered = True
            _LOGGER.debug("%s register AGAIN", entity.who)
            await entity.update_hass()
        else:
            _LOGGER.debug("%s register NEW", device.ip_addr)

            # Read initial state
            ack = AwaitAioLIFX().wait
            version_resp = await ack(device.get_version)
            if version_resp:
                color_resp = await ack(device.get_color)

            if version_resp is None or color_resp is None:
                _LOGGER.error("Failed to initialize %s", device.ip_addr)
            else:
                device.timeout = MESSAGE_TIMEOUT
                device.retry_count = MESSAGE_RETRIES
                device.unregister_timeout = UNAVAILABLE_GRACE

                if lifx_features(device)["multizone"]:
                    entity = LIFXStrip(device, self.effects_conductor)
                elif lifx_features(device)["color"]:
                    entity = LIFXColor(device, self.effects_conductor)
                else:
                    entity = LIFXWhite(device, self.effects_conductor)

                _LOGGER.debug("%s register READY", entity.who)
                self.entities[device.mac_addr] = entity
                self.async_add_devices([entity], True)

    @callback
    def unregister(self, device):
        """Handle aiolifx disappearing bulbs."""
        if device.mac_addr in self.entities:
            entity = self.entities[device.mac_addr]
            _LOGGER.debug("%s unregister", entity.who)
            entity.registered = False
            self.hass.async_add_job(entity.async_update_ha_state())


class AwaitAioLIFX:
    """Wait for an aiolifx callback and return the message."""

    def __init__(self):
        """Initialize the wrapper."""
        self.device = None
        self.message = None
        self.event = asyncio.Event()

    @callback
    def callback(self, device, message):
        """Handle responses."""
        self.device = device
        self.message = message
        self.event.set()

    async def wait(self, method):
        """Call an aiolifx method and wait for its response."""
        self.device = None
        self.message = None
        self.event.clear()
        method(callb=self.callback)

        await self.event.wait()
        return self.message


def convert_8_to_16(value):
    """Scale an 8 bit level into 16 bits."""
    return (value << 8) | value


def convert_16_to_8(value):
    """Scale a 16 bit level into 8 bits."""
    return value >> 8


class LIFXLight(Light):
    """Representation of a LIFX light."""

    def __init__(self, device, effects_conductor):
        """Initialize the light."""
        self.device = device
        self.effects_conductor = effects_conductor
        self.registered = True
        self.postponed_update = None
        self.lock = asyncio.Lock()

    @property
    def available(self):
        """Return the availability of the device."""
        return self.registered

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.device.mac_addr

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.label

    @property
    def who(self):
        """Return a string identifying the device."""
        return "%s (%s)" % (self.device.ip_addr, self.name)

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        kelvin = lifx_features(self.device)['max_kelvin']
        return math.floor(color_util.color_temperature_kelvin_to_mired(kelvin))

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        kelvin = lifx_features(self.device)['min_kelvin']
        return math.ceil(color_util.color_temperature_kelvin_to_mired(kelvin))

    @property
    def supported_features(self):
        """Flag supported features."""
        support = SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION | SUPPORT_EFFECT

        device_features = lifx_features(self.device)
        if device_features['min_kelvin'] != device_features['max_kelvin']:
            support |= SUPPORT_COLOR_TEMP

        return support

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        brightness = convert_16_to_8(self.device.color[2])
        _LOGGER.debug("brightness: %d", brightness)
        return brightness

    @property
    def color_temp(self):
        """Return the color temperature."""
        kelvin = self.device.color[3]
        temperature = color_util.color_temperature_kelvin_to_mired(kelvin)

        _LOGGER.debug("color_temp: %d", temperature)
        return temperature

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.device.power_level != 0

    @property
    def effect(self):
        """Return the name of the currently running effect."""
        effect = self.effects_conductor.effect(self.device)
        if effect:
            return 'lifx_effect_' + effect.name
        return None

    async def update_hass(self, now=None):
        """Request new status and push it to hass."""
        self.postponed_update = None
        await self.async_update()
        await self.async_update_ha_state()

    async def update_during_transition(self, when):
        """Update state at the start and end of a transition."""
        if self.postponed_update:
            self.postponed_update()

        # Transition has started
        await self.update_hass()

        # Transition has ended
        if when > 0:
            self.postponed_update = async_track_point_in_utc_time(
                self.hass, self.update_hass,
                util.dt.utcnow() + timedelta(milliseconds=when))

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        kwargs[ATTR_POWER] = True
        self.hass.async_add_job(self.set_state(**kwargs))

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        kwargs[ATTR_POWER] = False
        self.hass.async_add_job(self.set_state(**kwargs))

    async def set_state(self, **kwargs):
        """Set a color on the light and turn it on/off."""
        async with self.lock:
            bulb = self.device

            await self.effects_conductor.stop([bulb])

            if ATTR_EFFECT in kwargs:
                await self.default_effect(**kwargs)
                return

            if ATTR_INFRARED in kwargs:
                bulb.set_infrared(convert_8_to_16(kwargs[ATTR_INFRARED]))

            if ATTR_TRANSITION in kwargs:
                fade = int(kwargs[ATTR_TRANSITION] * 1000)
            else:
                fade = 0

            # These are both False if ATTR_POWER is not set
            power_on = kwargs.get(ATTR_POWER, False)
            power_off = not kwargs.get(ATTR_POWER, True)

            hsbk = find_hsbk(**kwargs)

            # Send messages, waiting for ACK each time
            ack = AwaitAioLIFX().wait

            if not self.is_on:
                if power_off:
                    await self.set_power(ack, False)
                if hsbk:
                    await self.set_color(ack, hsbk, kwargs)
                if power_on:
                    await self.set_power(ack, True, duration=fade)
            else:
                if power_on:
                    await self.set_power(ack, True)
                if hsbk:
                    await self.set_color(ack, hsbk, kwargs, duration=fade)
                if power_off:
                    await self.set_power(ack, False, duration=fade)

            # Avoid state ping-pong by holding off updates as the state settles
            await asyncio.sleep(0.3)

        # Update when the transition starts and ends
        await self.update_during_transition(fade)

    async def set_power(self, ack, pwr, duration=0):
        """Send a power change to the device."""
        await ack(partial(self.device.set_power, pwr, duration=duration))

    async def set_color(self, ack, hsbk, kwargs, duration=0):
        """Send a color change to the device."""
        hsbk = merge_hsbk(self.device.color, hsbk)
        await ack(partial(self.device.set_color, hsbk, duration=duration))

    async def default_effect(self, **kwargs):
        """Start an effect with default parameters."""
        service = kwargs[ATTR_EFFECT]
        data = {
            ATTR_ENTITY_ID: self.entity_id,
        }
        await self.hass.services.async_call(DOMAIN, service, data)

    async def async_update(self):
        """Update bulb status."""
        _LOGGER.debug("%s async_update", self.who)
        if self.available and not self.lock.locked():
            await AwaitAioLIFX().wait(self.device.get_color)


class LIFXWhite(LIFXLight):
    """Representation of a white-only LIFX light."""

    @property
    def effect_list(self):
        """Return the list of supported effects for this light."""
        return [
            SERVICE_EFFECT_PULSE,
            SERVICE_EFFECT_STOP,
        ]


class LIFXColor(LIFXLight):
    """Representation of a color LIFX light."""

    @property
    def supported_features(self):
        """Flag supported features."""
        support = super().supported_features
        support |= SUPPORT_COLOR
        return support

    @property
    def effect_list(self):
        """Return the list of supported effects for this light."""
        return [
            SERVICE_EFFECT_COLORLOOP,
            SERVICE_EFFECT_PULSE,
            SERVICE_EFFECT_STOP,
        ]

    @property
    def hs_color(self):
        """Return the hs value."""
        hue, sat, _, _ = self.device.color
        hue = hue / 65535 * 360
        sat = sat / 65535 * 100
        return (hue, sat)


class LIFXStrip(LIFXColor):
    """Representation of a LIFX light strip with multiple zones."""

    async def set_color(self, ack, hsbk, kwargs, duration=0):
        """Send a color change to the device."""
        bulb = self.device
        num_zones = len(bulb.color_zones)

        zones = kwargs.get(ATTR_ZONES)
        if zones is None:
            # Fast track: setting all zones to the same brightness and color
            # can be treated as a single-zone bulb.
            if hsbk[2] is not None and hsbk[3] is not None:
                await super().set_color(ack, hsbk, kwargs, duration)
                return

            zones = list(range(0, num_zones))
        else:
            zones = list(filter(lambda x: x < num_zones, set(zones)))

        # Zone brightness is not reported when powered off
        if not self.is_on and hsbk[2] is None:
            await self.set_power(ack, True)
            await asyncio.sleep(0.3)
            await self.update_color_zones()
            await self.set_power(ack, False)
            await asyncio.sleep(0.3)

        # Send new color to each zone
        for index, zone in enumerate(zones):
            zone_hsbk = merge_hsbk(bulb.color_zones[zone], hsbk)
            apply = 1 if (index == len(zones)-1) else 0
            set_zone = partial(bulb.set_color_zones,
                               start_index=zone,
                               end_index=zone,
                               color=zone_hsbk,
                               duration=duration,
                               apply=apply)
            await ack(set_zone)

    async def async_update(self):
        """Update strip status."""
        if self.available and not self.lock.locked():
            await super().async_update()
            await self.update_color_zones()

    async def update_color_zones(self):
        """Get updated color information for each zone."""
        zone = 0
        top = 1
        while self.available and zone < top:
            # Each get_color_zones can update 8 zones at once
            resp = await AwaitAioLIFX().wait(partial(
                self.device.get_color_zones,
                start_index=zone))
            if resp:
                zone += 8
                top = resp.count
