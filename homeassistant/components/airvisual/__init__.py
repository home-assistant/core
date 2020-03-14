"""The airvisual component."""
from datetime import timedelta
import logging

from pyairvisual import Client
from pyairvisual.errors import AirVisualError, InvalidKeyError, NotFoundError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_CITY,
    CONF_COUNTRY,
    CONF_GEOGRAPHIES,
    CONF_NODE_PRO_ID,
    DATA_CLIENT,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY,
    INTEGRATION_TYPE_NODE_PRO,
    TOPIC_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

DATA_LISTENER = "listener"

DEFAULT_ATTRIBUTION = "Data provided by AirVisual"
DEFAULT_GEOGRAPHY_SCAN_INTERVAL = timedelta(minutes=10)
DEFAULT_NODE_PRO_SCAN_INTERVAL = timedelta(minutes=1)
DEFAULT_OPTIONS = {CONF_SHOW_ON_MAP: True}

GEOGRAPHY_COORDINATES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LATITUDE): cv.latitude,
        vol.Required(CONF_LONGITUDE): cv.longitude,
    }
)

GEOGRAPHY_PLACE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CITY): cv.string,
        vol.Required(CONF_STATE): cv.string,
        vol.Required(CONF_COUNTRY): cv.string,
    }
)

CLOUD_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_GEOGRAPHIES, default=[]): vol.All(
            cv.ensure_list,
            [vol.Any(GEOGRAPHY_COORDINATES_SCHEMA, GEOGRAPHY_PLACE_SCHEMA)],
        ),
    }
)

NODE_PRO_SCHEMA = vol.Schema({vol.Required(CONF_NODE_PRO_ID): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [vol.Any(CLOUD_API_SCHEMA, NODE_PRO_SCHEMA)])},
    extra=vol.ALLOW_EXTRA,
)


@callback
def async_get_geography_id(geography_dict):
    """Generate a unique ID from a geography dict."""
    if CONF_CITY in geography_dict:
        return ", ".join(
            (
                geography_dict[CONF_CITY],
                geography_dict[CONF_STATE],
                geography_dict[CONF_COUNTRY],
            )
        )
    return ", ".join(
        (str(geography_dict[CONF_LATITUDE]), str(geography_dict[CONF_LONGITUDE]))
    )


async def async_setup(hass, config):
    """Set up the AirVisual component."""
    hass.data[DOMAIN] = {DATA_CLIENT: {}, DATA_LISTENER: {}}

    if DOMAIN not in config:
        return True

    for observable in config[DOMAIN]:
        if CONF_NODE_PRO_ID in observable:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=observable
                )
            )
        else:
            for geography in observable.get(
                CONF_GEOGRAPHIES,
                [
                    {
                        CONF_LATITUDE: hass.config.latitude,
                        CONF_LONGITUDE: hass.config.longitude,
                    }
                ],
            ):
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_IMPORT},
                        data={CONF_API_KEY: observable[CONF_API_KEY], **geography},
                    )
                )

    return True


@callback
def _standardize_geography_config_entry(hass, config_entry):
    """Ensure that geography observables have appropriate properties."""
    entry_updates = {}

    if not config_entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = config_entry.data[CONF_API_KEY]
    if not config_entry.options:
        # If the config entry doesn't already have any options set, set defaults:
        entry_updates["options"] = {CONF_SHOW_ON_MAP: True}

    if not entry_updates:
        return

    hass.config_entries.async_update_entry(config_entry, **entry_updates)


async def async_setup_entry(hass, config_entry):
    """Set up AirVisual as config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)

    if CONF_API_KEY in config_entry.data:
        _standardize_geography_config_entry(hass, config_entry)
        airvisual = AirVisualGeographyData(
            hass,
            Client(websession, api_key=config_entry.data[CONF_API_KEY]),
            config_entry,
        )

        # Only geography-based entries have options:
        config_entry.add_update_listener(async_update_options)
    else:
        airvisual = AirVisualNodeProData(
            hass, Client(websession), config_entry.data[CONF_NODE_PRO_ID]
        )

    try:
        await airvisual.async_update()
    except InvalidKeyError:
        _LOGGER.error("Invalid API key provided")
        raise ConfigEntryNotReady
    except NotFoundError:
        _LOGGER.error("Invalid Node/Pro ID provided")
        raise ConfigEntryNotReady

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = airvisual

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    async def refresh(event_time):
        """Refresh data from AirVisual."""
        await airvisual.async_update()

    hass.data[DOMAIN][DATA_LISTENER][config_entry.entry_id] = async_track_time_interval(
        hass, refresh, airvisual.scan_interval
    )

    return True


async def async_migrate_entry(hass, config_entry):
    """Migrate an old config entry."""
    version = config_entry.version

    _LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: One geography per config entry
    if version == 1:
        version = config_entry.version = 2

        # Update the config entry to only include the first geography (there is always
        # guaranteed to be at least one):
        geographies = list(config_entry.data[CONF_GEOGRAPHIES])
        first_geography = geographies.pop(0)
        first_id = async_get_geography_id(first_geography)

        hass.config_entries.async_update_entry(
            config_entry,
            unique_id=first_id,
            title=f"Cloud API ({first_id})",
            data={CONF_API_KEY: config_entry.data[CONF_API_KEY], **first_geography},
        )

        # For any geographies that remain, create a new config entry for each one:
        for geography in geographies:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={CONF_API_KEY: config_entry.data[CONF_API_KEY], **geography},
                )
            )

    _LOGGER.info("Migration to version %s successful", version)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an AirVisual config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)

    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(config_entry.entry_id)
    remove_listener()

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")

    return True


async def async_update_options(hass, config_entry):
    """Handle an options update."""
    airvisual = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
    airvisual.async_update_options(config_entry.options)


class AirVisualEntity(Entity):
    """Define a generic AirVisual entity."""

    def __init__(self, airvisual):
        """Initialize."""
        self._airvisual = airvisual
        self._async_unsub_dispatcher_connect = None
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = None
        self._unit = None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._airvisual.topic_update, update)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
            self._async_unsub_dispatcher_connect = None


class AirVisualGeographyData:
    """Define a class to manage data from the AirVisual cloud API."""

    def __init__(self, hass, client, config_entry):
        """Initialize."""
        self._client = client
        self._hass = hass
        self.data = {}
        self.geography_data = config_entry.data
        self.geography_id = config_entry.unique_id
        self.integration_type = INTEGRATION_TYPE_GEOGRAPHY
        self.options = config_entry.options
        self.scan_interval = DEFAULT_GEOGRAPHY_SCAN_INTERVAL
        self.topic_update = TOPIC_UPDATE.format(config_entry.unique_id)

    async def async_update(self):
        """Get new data for all locations from the AirVisual cloud API."""
        if CONF_CITY in self.geography_data:
            api_coro = self._client.api.city(
                self.geography_data[CONF_CITY],
                self.geography_data[CONF_STATE],
                self.geography_data[CONF_COUNTRY],
            )
        else:
            api_coro = self._client.api.nearest_city(
                self.geography_data[CONF_LATITUDE], self.geography_data[CONF_LONGITUDE],
            )

        try:
            self.data[self.geography_id] = await api_coro
        except AirVisualError as err:
            _LOGGER.error("Error while retrieving data: %s", err)
            self.data[self.geography_id] = {}

        _LOGGER.debug("Received new geography data")
        async_dispatcher_send(self._hass, self.topic_update)

    @callback
    def async_update_options(self, options):
        """Update the data manager's options."""
        self.options = options
        async_dispatcher_send(self._hass, self.topic_update)


class AirVisualNodeProData:
    """Define a class to manage data from an AirVisual Node/Pro."""

    def __init__(self, hass, client, node_pro_id):
        """Initialize."""
        self._client = client
        self._hass = hass
        self.data = {}
        self.integration_type = INTEGRATION_TYPE_NODE_PRO
        self.node_pro_id = node_pro_id
        self.scan_interval = DEFAULT_NODE_PRO_SCAN_INTERVAL
        self.topic_update = TOPIC_UPDATE.format(node_pro_id)

    async def async_update(self):
        """Get new data from the Node/Pro."""
        try:
            self.data = await self._client.api.node(self.node_pro_id)
        except AirVisualError as err:
            _LOGGER.error("Error while retrieving Node/Pro data: %s", err)
            self.data = {}

        _LOGGER.debug("Received new Node/Pro data")
        async_dispatcher_send(self._hass, self.topic_update)
