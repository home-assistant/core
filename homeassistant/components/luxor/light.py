"""Light support for FX Luminaire Luxor low voltage controller integration."""

from datetime import timedelta
import logging

from aiohttp import client_exceptions as aio_exceptions
import async_timeout
from luxor import LuxorError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_INCLUDE_LUXOR_THEMES,
    DEFAULT_INCLUDE_LUXOR_THEMES,
    DOMAIN as LUXOR_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Luxor light platform.

    Adds groups and themes from the Luxor controller as light entities.
    """
    client = hass.data[LUXOR_DOMAIN][config_entry.entry_id]

    async def async_update_group_data():
        """Fetch group data from Luxor controller."""
        groups = await async_safe_fetch(client.get_groups)
        return {group["Grp"]: group for group in groups}

    light_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="luxor",
        update_method=async_update_group_data,
        update_interval=timedelta(seconds=1),
    )

    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    await light_coordinator.async_config_entry_first_refresh()

    entities = [
        LuxorGroupLightEntity(light_coordinator, client, group_id)
        for group_id in light_coordinator.data.keys()
    ]
    async_add_entities(entities)

    #
    # Add Luxor themes as lights, if configured to do so.
    # Users might want avoid adding them if they do things like 'turn on all lights'
    # that will result in enabling all the themes in parellel, which is not ideal.
    #
    async def async_update_theme_data():
        """Fetch theme data from Luxor controller."""
        themes = await async_safe_fetch(client.get_themes)
        return {theme["ThemeIndex"]: theme for theme in themes}

    include_luxor_themes = config_entry.options.get(
        CONF_INCLUDE_LUXOR_THEMES, DEFAULT_INCLUDE_LUXOR_THEMES
    )

    if include_luxor_themes:
        theme_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="luxor",
            update_method=async_update_theme_data,
            update_interval=timedelta(seconds=1),
        )

        await theme_coordinator.async_config_entry_first_refresh()

        entities = [
            LuxorThemeLightEntity(theme_coordinator, client, theme_id)
            for theme_id in theme_coordinator.data.keys()
        ]
        async_add_entities(entities)

    return True


async def async_safe_fetch(method):
    """Safely fetch data."""
    try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator
        async with async_timeout.timeout(10):
            return await method()
    except aio_exceptions.ClientConnectorError as err:
        raise UpdateFailed(f"Connection error: {err}")
    except LuxorError as err:
        raise UpdateFailed(f"Error communicating with API: {err}")


def luxor_brightness_to_hass(value):
    """Convert luxor brightness 1..100 to hass format 0..255."""
    return int((value * 255) // 100)


def hass_to_luxor_brightness(value):
    """Convert hass brightness 0..255 to luxor 1..100 scale."""
    return int(round((value * 100) / 255))


class LuxorGroupLightEntity(CoordinatorEntity, LightEntity):
    """Representation of a Luxor light group as a homeassisant light entity."""

    def __init__(self, coordinator, client, group_id):
        """Initialize the light."""
        super().__init__(coordinator)
        self.client = client
        self.group_id = group_id

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return luxor_brightness_to_hass(self._data["Inten"])

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._data["Inten"] > 0

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            intensity = hass_to_luxor_brightness(kwargs[ATTR_BRIGHTNESS])
        else:
            intensity = 100

        await self.client.illuminate_group(self.group_id, intensity=intensity)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.client.illuminate_group(self.group_id, intensity=0)
        await self.coordinator.async_request_refresh()

    @property
    def name(self):
        """Return the name of the Luxor group."""
        return self._data["Name"]

    @property
    def _data(self):
        return self.coordinator.data[self.group_id]


class LuxorThemeLightEntity(CoordinatorEntity, LightEntity):
    """Representation of a Luxor theme as a homeassisant light entity."""

    def __init__(self, coordinator, client, theme_id):
        """Initialize the light."""
        super().__init__(coordinator)
        self.client = client
        self.theme_id = theme_id

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._data["OnOff"] > 0

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        await self.client.illuminate_theme(self.theme_id, on_off=1)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.client.illuminate_theme(self.theme_id, on_off=0)
        await self.coordinator.async_request_refresh()

    @property
    def name(self):
        """Return the name of the Luxor theme."""
        return "(Theme) " + self._data["Name"]

    @property
    def _data(self):
        return self.coordinator.data[self.theme_id]
