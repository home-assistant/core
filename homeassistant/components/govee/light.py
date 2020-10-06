"""Govee LED strips platform."""

from datetime import timedelta
import logging

from govee_api_laggat import Govee, GoveeDevice, GoveeError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.const import CONF_DELAY
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import color

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Govee Light platform."""
    _LOGGER.debug("Setting up Govee lights")
    config = entry.data
    hub = hass.data[DOMAIN]["hub"]

    # refresh
    update_interval = timedelta(seconds=config[CONF_DELAY])
    coordinator = GoveeDataUpdateCoordinator(
        hass, _LOGGER, update_interval=update_interval
    )
    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    # Add devices
    async_add_entities(
        [
            GoveeLightEntity(hub, entry.title, coordinator, device)
            for device in hub.devices
        ],
        update_before_add=False,
    )


class GoveeDataUpdateCoordinator(DataUpdateCoordinator):
    """Device state update handler."""

    def __init__(
        self,
        hass,
        logger,
        update_interval=None,
    ):
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval,
            update_method=self._async_update,
        )

    async def _async_update(self):
        """Fetch data."""
        self.logger.debug("_async_update")
        if "govee" not in self.hass.data:
            raise UpdateFailed("Govee instance not available")
        try:
            hub = self.hass.data[DOMAIN]["hub"]

            if not hub.online:
                # when offline, check connection, this will set hub.online
                await hub.check_connection()

            if hub.online:
                # govee will change this to a single request in 2021
                device_states = await hub.get_states()
                for device in device_states:
                    if device.error:
                        self.logger.warning(
                            "update failed for %s: %s", device.device, device.error
                        )
                return device_states
        except GoveeError as ex:
            raise UpdateFailed(f"Exception on getting states: {ex}") from ex


class GoveeLightEntity(LightEntity):
    """Representation of a stateful light entity."""

    def __init__(
        self,
        hub: Govee,
        title: str,
        coordinator: GoveeDataUpdateCoordinator,
        device: GoveeDevice,
    ):
        """Init a Govee light strip."""
        self._hub = hub
        self._title = title
        self._coordinator = coordinator
        self._device = device

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def _state(self):
        """Lights internal state."""
        return self._device  # self._hub.state(self._device)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP

    async def async_turn_on(self, **kwargs):
        """Turn device on."""
        _LOGGER.debug(
            "async_turn_on for Govee light %s, kwargs: %s", self._device.device, kwargs
        )
        err = None

        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            col = color.color_hs_to_RGB(hs_color[0], hs_color[1])
            _, err = await self._hub.set_color(self._device, col)
        elif ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            bright_set = brightness - 1
            _, err = await self._hub.set_brightness(self._device, bright_set)
        elif ATTR_COLOR_TEMP in kwargs:
            color_temp = kwargs[ATTR_COLOR_TEMP]
            _, err = await self._hub.set_color_temp(self._device, color_temp)
            # color_temp is not in state
        else:
            _, err = await self._hub.turn_on(self._device)
        # warn on any error
        if err:
            _LOGGER.warning(
                "async_turn_on failed with '%s' for %s, kwargs: %s",
                err,
                self._device.device,
                kwargs,
            )

    async def async_turn_off(self, **kwargs):
        """Turn device off."""
        _LOGGER.debug("async_turn_off for Govee light %s", self._device.device)
        await self._hub.turn_off(self._device)

    @property
    def unique_id(self):
        """Return the unique ID."""
        return f"govee_{self._title}_{self._device.device}"

    @property
    def device_id(self):
        """Return the ID."""
        return self.unique_id

    @property
    def name(self):
        """Return the name."""
        return self._device.device_name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": "Govee",
            "model": self._device.model,
            "via_device": (DOMAIN, "Govee API (cloud)"),
        }

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.power_state

    @property
    def assumed_state(self):
        """Return true if the state is assumed."""
        return self._device.source == "history"

    @property
    def available(self):
        """Return if light is available."""
        return self._device.online

    @property
    def hs_color(self):
        """Return the hs color value."""
        return color.color_RGB_to_hs(
            self._device.color[0],
            self._device.color[1],
            self._device.color[2],
        )

    @property
    def rgb_color(self):
        """Return the rgb color value."""
        return [
            self._device.color[0],
            self._device.color[1],
            self._device.color[2],
        ]

    @property
    def brightness(self):
        """Return the brightness value."""
        # govee is reporting 0 to 254 - home assistant uses 1 to 255
        return self._device.brightness + 1

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return 2000

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return 9000

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            # rate limiting information on Govee API
            "rate_limit_total": self._hub.rate_limit_total,
            "rate_limit_remaining": self._hub.rate_limit_remaining,
            "rate_limit_reset_seconds": self._hub.rate_limit_reset_seconds,
            "rate_limit_reset": self._hub.rate_limit_reset,
            "rate_limit_on": self._hub.rate_limit_on,
            # general information
            "manufacturer": "Govee",
            "model": self._device.model,
        }
