"""Support for Brunt Blind Engine covers."""

from datetime import timedelta
import logging

from aiohttp.client_exceptions import ClientResponseError, ServerDisconnectedError
import async_timeout
from brunt import BruntClientAsync, Thing

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_WINDOW,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_REQUEST_POSITION,
    ATTRIBUTION,
    CLOSED_POSITION,
    DOMAIN,
    OPEN_POSITION,
)

_LOGGER = logging.getLogger(__name__)

COVER_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION
REGULAR_INTERVAL = timedelta(seconds=20)
FAST_INTERVAL = timedelta(seconds=1)


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    """Set up the brunt platform."""
    bapi: BruntClientAsync = hass.data[DOMAIN][entry.entry_id]

    async def async_update_data():
        """Fetch data from the Brunt endpoint for all Things."""
        try:
            async with async_timeout.timeout(10):
                things = await bapi.async_get_things(force=True)
                return {thing.SERIAL: thing for thing in things}
        except ServerDisconnectedError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except ClientResponseError as err:
            if err.status == 403:
                raise ConfigEntryAuthFailed() from err
            if err.status == 401:
                raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            raise UpdateFailed("Unknown error.") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="brunt",
        update_method=async_update_data,
        update_interval=REGULAR_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        BruntDevice(coordinator, serial, thing, bapi, entry.entry_id)
        for serial, thing in coordinator.data.items()
    )
    return True


class BruntDevice(CoordinatorEntity, CoverEntity):
    """
    Representation of a Brunt cover device.

    Contains the common logic for all Brunt devices.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        serial: str,
        thing: Thing,
        bapi: BruntClientAsync,
        entry_id: str,
    ):
        """Init the Brunt device."""
        super().__init__(coordinator)
        self._unique_id = serial
        self._bapi = bapi
        self._thing = thing
        self._entry_id = entry_id
        self._remove_update_listener = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._brunt_update_listener)
        )

    @property
    def unique_id(self) -> str:
        """Get unique_id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device as reported by tellcore."""
        return self._thing.NAME

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        pos = self.coordinator.data[self._unique_id].currentPosition
        return int(pos) if pos else None

    @property
    def request_cover_position(self) -> int | None:
        """
        Return request position of cover.

        The request position is the position of the last request
        to Brunt, at times there is a diff of 1 to current
        None is unknown, 0 is closed, 100 is fully open.
        """
        pos = self.coordinator.data[self._unique_id].requestPosition
        return int(pos) if pos else None

    @property
    def move_state(self) -> int | None:
        """
        Return current moving state of cover.

        None is unknown, 0 when stopped, 1 when opening, 2 when closing
        """
        mov = self.coordinator.data[self._unique_id].moveState
        return int(mov) if mov else None

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self.move_state == 1

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self.move_state == 2

    @property
    def extra_state_attributes(self):
        """Return the detailed device state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_REQUEST_POSITION: self.request_cover_position,
        }

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_WINDOW

    @property
    def supported_features(self):
        """Flag supported features."""
        return COVER_FEATURES

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self.current_cover_position == CLOSED_POSITION

    async def async_open_cover(self, **kwargs):
        """Set the cover to the open position."""
        await self._async_update_cover(OPEN_POSITION)

    async def async_close_cover(self, **kwargs):
        """Set the cover to the closed position."""
        await self._async_update_cover(CLOSED_POSITION)

    async def async_set_cover_position(self, **kwargs):
        """Set the cover to a specific position."""
        await self._async_update_cover(kwargs[ATTR_POSITION])

    async def _async_update_cover(self, position):
        """Set the cover to the new position and wait for the update to be reflected."""
        try:
            await self._bapi.async_change_request_position(
                position, thingUri=self._thing.thingUri
            )
        except ClientResponseError:
            _LOGGER.warning("Unable to reposition %s", self._thing.NAME)
            return
        self.coordinator.update_interval = FAST_INTERVAL
        await self.coordinator.async_request_refresh()

    @callback
    def _brunt_update_listener(self):
        """Update the update interval after each refresh."""
        if (
            self.request_cover_position
            == self._bapi.last_requested_positions[self._thing.thingUri]
            and self.move_state == 0
        ):
            self.coordinator.update_interval = REGULAR_INTERVAL
        else:
            self.coordinator.update_interval = FAST_INTERVAL

    @property
    def device_info(self) -> dict:
        """Return the device_info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "via_device": (DOMAIN, self._entry_id),
            "manufacturer": "Brunt",
            "sw_version": self._thing.FW_VERSION,
            "model": self._thing.MODEL,
        }
