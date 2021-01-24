"""Support for FluxLED/MagicHome lights."""

from datetime import timedelta
import logging
import random

from flux_led import WifiLedBulb
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_MODE, CONF_HOST, CONF_NAME, CONF_PROTOCOL
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_DEVICES,
    CONF_EFFECT_SPEED,
    DEFAULT_EFFECT_SPEED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_CUSTOM_EFFECT = "custom_effect"
CONF_COLORS = "colors"
CONF_SPEED_PCT = "speed_pct"
CONF_TRANSITION = "transition"
CONF_CUSTOM_EFFECT = "custom_effect"

SUPPORT_FLUX_LED = SUPPORT_BRIGHTNESS | SUPPORT_EFFECT | SUPPORT_COLOR

MODE_RGB = "rgb"
MODE_WHITE = "w"

# List of supported effects which aren't already declared in LIGHT
EFFECT_RED_FADE = "red_fade"
EFFECT_GREEN_FADE = "green_fade"
EFFECT_BLUE_FADE = "blue_fade"
EFFECT_YELLOW_FADE = "yellow_fade"
EFFECT_CYAN_FADE = "cyan_fade"
EFFECT_PURPLE_FADE = "purple_fade"
EFFECT_WHITE_FADE = "white_fade"
EFFECT_RED_GREEN_CROSS_FADE = "rg_cross_fade"
EFFECT_RED_BLUE_CROSS_FADE = "rb_cross_fade"
EFFECT_GREEN_BLUE_CROSS_FADE = "gb_cross_fade"
EFFECT_COLORSTROBE = "colorstrobe"
EFFECT_RED_STROBE = "red_strobe"
EFFECT_GREEN_STROBE = "green_strobe"
EFFECT_BLUE_STROBE = "blue_strobe"
EFFECT_YELLOW_STROBE = "yellow_strobe"
EFFECT_CYAN_STROBE = "cyan_strobe"
EFFECT_PURPLE_STROBE = "purple_strobe"
EFFECT_WHITE_STROBE = "white_strobe"
EFFECT_COLORJUMP = "colorjump"
EFFECT_CUSTOM = "custom"

EFFECT_MAP = {
    EFFECT_COLORLOOP: 0x25,
    EFFECT_RED_FADE: 0x26,
    EFFECT_GREEN_FADE: 0x27,
    EFFECT_BLUE_FADE: 0x28,
    EFFECT_YELLOW_FADE: 0x29,
    EFFECT_CYAN_FADE: 0x2A,
    EFFECT_PURPLE_FADE: 0x2B,
    EFFECT_WHITE_FADE: 0x2C,
    EFFECT_RED_GREEN_CROSS_FADE: 0x2D,
    EFFECT_RED_BLUE_CROSS_FADE: 0x2E,
    EFFECT_GREEN_BLUE_CROSS_FADE: 0x2F,
    EFFECT_COLORSTROBE: 0x30,
    EFFECT_RED_STROBE: 0x31,
    EFFECT_GREEN_STROBE: 0x32,
    EFFECT_BLUE_STROBE: 0x33,
    EFFECT_YELLOW_STROBE: 0x34,
    EFFECT_CYAN_STROBE: 0x35,
    EFFECT_PURPLE_STROBE: 0x36,
    EFFECT_WHITE_STROBE: 0x37,
    EFFECT_COLORJUMP: 0x38,
}
EFFECT_CUSTOM_CODE = 0x60

TRANSITION_GRADUAL = "gradual"
TRANSITION_JUMP = "jump"
TRANSITION_STROBE = "strobe"

FLUX_EFFECT_LIST = sorted(list(EFFECT_MAP)) + [EFFECT_RANDOM]

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform and manage importing from YAML."""
    automatic_add = config["automatic_add"]
    devices = {}

    for import_host, import_item in config["devices"].items():
        import_name = import_host
        import_name = import_item.get("name", import_host)

        devices[import_host.replace(".", "_")] = {
            CONF_NAME: import_name,
            CONF_HOST: import_host,
        }

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_AUTOMATIC_ADD: automatic_add,
            CONF_DEVICES: devices,
        },
    )

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Flux lights."""

    async def async_new_lights(bulbs: dict):
        """Add new bulbs when they are found or configured."""

        lights = []

        for bulb_id, bulb_details in bulbs.items():
            effect_speed = entry.options.get(bulb_id, {}).get(
                CONF_EFFECT_SPEED,
                entry.options.get("global", {}).get(
                    CONF_EFFECT_SPEED, DEFAULT_EFFECT_SPEED
                ),
            )

            host = bulb_details[CONF_HOST]
            try:
                bulb = await hass.async_add_executor_job(WifiLedBulb, host)
            except BrokenPipeError as error:
                raise PlatformNotReady(error) from error

            lights.append(
                FluxLight(
                    unique_id=bulb_id,
                    device=bulb_details,
                    effect_speed=effect_speed,
                    bulb=bulb,
                )
            )

        async_add_entities(lights, True)

    await async_new_lights(entry.data[CONF_DEVICES])

    async_dispatcher_connect(hass, SIGNAL_ADD_DEVICE, async_new_lights)

class FluxLight(LightEntity):
    """Representation of a Flux light."""

    def __init__(self, device):
        """Initialize the light."""
        self._name = device["name"]
        self._ipaddr = device[CONF_HOST]
        self._protocol = device[CONF_PROTOCOL]
        self._mode = device[ATTR_MODE]
        self._custom_effect = device[CONF_CUSTOM_EFFECT]
        self._effect_speed = device[CONF_EFFECT_SPEED]
        self._bulb = None
        self._error_reported = False

    def _connect(self):
        """Connect to Flux light."""

        self._bulb = WifiLedBulb(self._ipaddr, timeout=5)
        if self._protocol:
            self._bulb.setProtocol(self._protocol)

        # After bulb object is created the status is updated. We can
        # now set the correct mode if it was not explicitly defined.
        if not self._mode:
            if self._bulb.rgbwcapable:
                self._mode = MODE_RGBW
            else:
                self._mode = MODE_RGB

    def _disconnect(self):
        """Disconnect from Flux light."""
        self._bulb = None


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Flux lights."""

    async def async_new_lights(bulbs: dict):
        """Add new bulbs when they are found or configured."""

        lights = []

        for bulb_id, bulb_details in bulbs.items():
            effect_speed = entry.options.get(bulb_id, {}).get(
                CONF_EFFECT_SPEED,
                entry.options.get("global", {}).get(
                    CONF_EFFECT_SPEED, DEFAULT_EFFECT_SPEED
                ),
            )

    if config_auto:
        # Find the bulbs on the LAN
        scanner = BulbScanner()
        await hass.async_add_executor_job(scanner.scan)

        for device in scanner.getBulbInfo():
            device_id = device["ipaddr"].replace(".", "_")
                hass=hass,
                name=bulb_details[CONF_NAME],
                update_interval=DEFAULT_SCAN_INTERVAL,
                ip_address=bulb_details[CONF_HOST],
                scan_coordinator=bulb_coordinator,
            )

            await coordinator.async_refresh()

            lights.append(
                FluxLight(
                    coordinator=coordinator,
                    unique_id=bulb_id,
                    device=bulb_details,
                    effect_speed=effect_speed,
                    hass=hass,
                )
            )

        async_add_entities(lights)

    await async_new_lights(entry.data[CONF_DEVICES])

    async_dispatcher_connect(hass, SIGNAL_ADD_DEVICE, async_new_lights)


class FluxLEDCoordinator(DataUpdateCoordinator):
    """Update Coordinator for a specific light entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        update_interval: int,
        ip_address: str,
        scan_coordinator: FluxLEDListUpdateCoordinator = None,
    ):
        """Initialize the update coordinator."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=timedelta(milliseconds=update_interval),
        )

        self._ip_address = ip_address
        self._name = name
        self.scan_coordinator = scan_coordinator

        self.light = WifiLedBulb(self._ip_address)

    async def _async_update_data(self):
        """Fetch the data from this light bulb."""

        await self.hass.async_add_executor_job(self.light.update_state)

        get_rgbw = await self.hass.async_add_executor_job(self.light.getRgbw)
        get_rgb = await self.hass.async_add_executor_job(self.light.getRgb)

        light = {}

        if self.light.mode == "ww":
            light["mode"] = MODE_WHITE
        elif self.light.rgbwcapable:
            light["mode"] = MODE_RGBW
        else:
            light["mode"] = MODE_RGB

        light["white_value"] = get_rgbw[3]

        if light["mode"] == MODE_WHITE:
            light["brightness"] = light["white_value"]
        else:
            light["brightness"] = self.light.brightness

        light["hs_color"] = color_util.color_RGB_to_hs(*get_rgb)

        light["current_effect"] = self.light.raw_state[3]

        if self.light.is_on and light["brightness"] > 0:
            light["state"] = True
        else:
            light["state"] = False

        return light


class FluxLight(CoordinatorEntity, LightEntity):
    """Represents a Flux Light entity."""

    def __init__(
        self,
        coordinator: FluxLEDCoordinator,
        unique_id: str,
        device: dict,
        effect_speed: int,
        hass: HomeAssistant,
    ):
        """Initialize the Flux light entity."""
        super().__init__(coordinator=coordinator)

        self._name = device[CONF_NAME]
        self._unique_id = unique_id
        self._icon = "mdi:lightbulb"
        self._attrs = {}
        self._last_update = 0
        self._state = None
        self._brightness = None
        self._hs_color = None
        self._bulb = coordinator.light
        self._last_brightness = 255
        self._last_hs_color = color_util.color_RGB_to_hs(255, 255, 255)
        self._ip_address = device[CONF_HOST]
        self._effect_speed = effect_speed
        self._mode = coordinator.data["mode"]

        async def async_remove_light(device: dict):
            """Remove a bulb device when it is removed from options."""

            bulb_id = device["device_id"]

            if self._unique_id != bulb_id:
                return

            entity_registry = await hass.helpers.entity_registry.async_get_registry()
            entity_entry = entity_registry.async_get(self.entity_id)

            device_registry = await hass.helpers.device_registry.async_get_registry()
            device_entry = device_registry.async_get(entity_entry.device_id)

            if (
                len(
                    async_entries_for_device(
                        entity_registry,
                        entity_entry.device_id,
                        include_disabled_entities=True,
                    )
                )
                == 1
            ):
                device_registry.async_remove_device(device_entry.id)

            entity_registry.async_remove(self.entity_id)

        async_dispatcher_connect(hass, SIGNAL_REMOVE_DEVICE, async_remove_light)

    @property
    def unique_id(self):
        """Return the unique ID of the light."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def is_on(self):
        return self._state

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs_color

    @property
    def white_value(self):
        """Return the white value of this light."""
        return self._white_value

    @property
    def supported_features(self):
        """Return the supported features for this light."""
        if self._mode == MODE_RGBW:
            return SUPPORT_FLUX_LED | SUPPORT_WHITE_VALUE

        return SUPPORT_FLUX_LED

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return FLUX_EFFECT_LIST + [EFFECT_CUSTOM]

    @property
    def effect(self):
        """Return the current effect."""
        current_mode = self._current_effect

        if current_mode == EFFECT_CUSTOM_CODE:
            return EFFECT_CUSTOM

        for effect, code in EFFECT_MAP.items():
            if current_mode == code:
                return effect

        return None

    @property
    def device_state_attributes(self):
        """Return the attributes."""
        self._attrs["ip_address"] = self._ip_address

        return self._attrs

    @property
    def device_info(self):
        """Return the device information."""
        device_name = "FluxLED/Magic Home"
        device_model = "LED Lights"

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._unique_id)},
            ATTR_NAME: self._name,
            ATTR_MANUFACTURER: device_name,
            ATTR_MODEL: device_model,
        }

    def turn_on(self, **kwargs):
        """Turn on the light."""
        rgb = None

        hs_color = kwargs.get(ATTR_HS_COLOR)

        if hs_color:
            rgb = color_util.color_hs_to_RGB(*hs_color)

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        white = kwargs.get(ATTR_WHITE_VALUE)

        if effect == EFFECT_RANDOM:
            color_red = random.randint(0, 255)
            color_green = random.randint(0, 255)
            color_blue = random.randint(0, 255)

            self._bulb.setRgbw(
                r=color_red,
                g=color_green,
                b=color_blue,
            )

            self._hs_color = color_util.color_RGB_to_hs(
                color_red,
                color_green,
                color_blue,
            )

            return

        if effect in EFFECT_MAP:
<<<<<<< HEAD
<<<<<<< HEAD
            self._bulb.setPresetPattern(EFFECT_MAP[effect], self._effect_speed)
            return
=======
<<<<<<< HEAD
>>>>>>> Refactor flux led and add config_flow (#44320)
=======
>>>>>>> Addressed PR comments.
            self._bulb.setPresetPattern(EFFECT_MAP[effect], DEFAULT_SPEED)

        if not brightness:
            brightness = self._last_brightness

        self._brightness = brightness
<<<<<<< HEAD
<<<<<<< HEAD
            self._bulb.setPresetPattern(EFFECT_MAP[effect], 50)
            return

        self._last_brightness = brightness
        self._brightness = brightness
=======
=======
            self._bulb.setPresetPattern(EFFECT_MAP[effect], self._effect_speed)
            return
>>>>>>> Refactor flux led and add config_flow (#44320)
>>>>>>> Refactor flux led and add config_flow (#44320)
=======
>>>>>>> Addressed PR comments.

        if not rgb:
            rgb = color_util.color_hs_to_RGB(*self._last_hs_color)

        self._hs_color = color_util.color_RGB_to_hs(*tuple(rgb))

        if not white and self._mode == MODE_RGBW:
            white = self.white_value

        self._state = True
        self._hs_color = color_util.color_RGB_to_hs(*tuple(rgb))

        if self._mode == MODE_WHITE:
            self._bulb.setRgbw(0, 0, 0, w=brightness)

        elif self._mode == MODE_RGBW:
            self._bulb.setRgbw(*tuple(rgb), w=white, brightness=brightness)

        else:
            self._bulb.setRgb(*tuple(rgb), brightness=brightness)

    def turn_off(self, **kwargs):
        """Turn off the light."""

        self._last_brightness = self.brightness
        self._last_hs_color = self.hs_color

        self._state = False

        self._bulb.turnOff()
