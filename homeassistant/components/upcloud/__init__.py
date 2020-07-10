"""Support for UpCloud."""

import dataclasses
from datetime import timedelta
import logging
from typing import Dict, List, Optional

import requests.exceptions
import upcloud_api
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_PROBLEM,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt

from .const import CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_CORE_NUMBER = "core_number"
ATTR_HOSTNAME = "hostname"
ATTR_MEMORY_AMOUNT = "memory_amount"
ATTR_STATE = "state"
ATTR_TITLE = "title"
ATTR_UUID = "uuid"
ATTR_ZONE = "zone"

CONF_SERVERS = "servers"

DATA_UPCLOUD = "data_upcloud"

DEFAULT_COMPONENT_NAME = "UpCloud {}"
DEFAULT_COMPONENT_DEVICE_CLASS = "power"

CONFIG_ENTRY_DOMAINS = {BINARY_SENSOR_DOMAIN, SWITCH_DOMAIN}

SIGNAL_UPDATE_UPCLOUD = "upcloud_update"

STATE_MAP = {"error": STATE_PROBLEM, "started": STATE_ON, "stopped": STATE_OFF}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config) -> bool:
    """Set up UpCloud component."""
    _LOGGER.warning(
        "Loading upcloud via top level config is deprecated and no longer "
        "necessary as of 0.114. Please remove it from your YAML configuration."
    )
    domain_config = config.get(DOMAIN)
    if domain_config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_USERNAME: domain_config[CONF_USERNAME],
                    CONF_PASSWORD: domain_config[CONF_PASSWORD],
                },
            )
        )

        if domain_config[CONF_SCAN_INTERVAL]:
            # Migrate scan interval config as an option: populate a UpCloudData to be
            # picked up by config entry setup later.
            hass.data.setdefault(DATA_UPCLOUD, {})[
                domain_config[CONF_USERNAME]
            ] = UpCloudData(
                upcloud=UpCloud(  # unused, but set here because it's required
                    hass=hass,
                    manager=upcloud_api.CloudManager(
                        domain_config[CONF_USERNAME], domain_config[CONF_PASSWORD]
                    ),
                ),
                scan_interval=domain_config[CONF_SCAN_INTERVAL],
            )
    return True


@dataclasses.dataclass
class UpCloudData:
    """Data related to single UpCloud config entry."""

    upcloud: "UpCloud"
    scan_interval: timedelta
    unload_scan_handler: Optional[CALLBACK_TYPE] = None
    unload_handlers: List[CALLBACK_TYPE] = dataclasses.field(default_factory=list)

    def async_update_config(self, config_entry: ConfigEntry) -> None:
        """Handle config update."""
        self.scan_interval = timedelta(seconds=config_entry.options[CONF_SCAN_INTERVAL])
        self.async_init_scan()

    def async_init_scan(self) -> None:
        """Initialize polling."""
        if self.unload_scan_handler:
            self.unload_scan_handler()
        self.unload_scan_handler = async_track_time_interval(
            self.upcloud.hass, self.upcloud.async_update, self.scan_interval
        )

    def cleanup(self, *_) -> None:
        """Clean up resources."""
        while self.unload_handlers:
            self.unload_handlers.pop(0)()
        if self.unload_scan_handler:
            self.unload_scan_handler()
            self.unload_scan_handler = None


def _config_entry_update_signal_name(config_entry: ConfigEntry) -> str:
    """Get signal name for updates to a config entry."""
    return CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE.format(config_entry.unique_id)


async def _async_signal_options_update(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> None:
    """Signal config entry options update."""
    async_dispatcher_send(
        hass, _config_entry_update_signal_name(config_entry), config_entry
    )


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Set up the UpCloud config entry."""

    manager = upcloud_api.CloudManager(
        config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD]
    )

    try:
        await hass.async_add_executor_job(manager.authenticate)
    except upcloud_api.UpCloudAPIError:
        _LOGGER.error("Authentication failed", exc_info=True)
        return False
    except requests.exceptions.RequestException:
        _LOGGER.error("Failed to connect", exc_info=True)
        raise ConfigEntryNotReady

    upcloud_data = UpCloudData(
        upcloud=UpCloud(hass=hass, manager=manager),
        scan_interval=timedelta(seconds=config_entry.options.get(CONF_SCAN_INTERVAL))
        if config_entry.options.get(CONF_SCAN_INTERVAL)
        else DEFAULT_SCAN_INTERVAL,
    )

    upcloud_data.unload_handlers.append(
        config_entry.add_update_listener(_async_signal_options_update),
    )
    upcloud_data.unload_handlers.append(
        async_dispatcher_connect(
            hass,
            _config_entry_update_signal_name(config_entry),
            upcloud_data.async_update_config,
        )
    )

    connections = hass.data.setdefault(DATA_UPCLOUD, {})

    # Handle pre config entry scan interval migration to options
    migrated_data = connections.get(config_entry.data[CONF_USERNAME])
    if (
        migrated_data
        and migrated_data.scan_interval
        and (
            not config_entry.options.get(CONF_SCAN_INTERVAL)
            or config_entry.options.get(CONF_SCAN_INTERVAL)
            == DEFAULT_SCAN_INTERVAL.seconds
        )
    ):
        upcloud_data.scan_interval = migrated_data.scan_interval
        hass.config_entries.async_update_entry(
            config_entry,
            options={CONF_SCAN_INTERVAL: upcloud_data.scan_interval.seconds},
        )
    else:
        upcloud_data.async_init_scan()

    connections[config_entry.data[CONF_USERNAME]] = upcloud_data

    # Call the UpCloud API to refresh data
    await upcloud_data.upcloud.async_update(dt.utcnow())

    # Forward entry setup
    for domain in CONFIG_ENTRY_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, domain)
        )

    # Clean up at end
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, upcloud_data.cleanup)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload the config entry."""
    for domain in CONFIG_ENTRY_DOMAINS:
        await hass.config_entries.async_forward_entry_unload(config_entry, domain)

    data = hass.data[DATA_UPCLOUD].pop(config_entry.data[CONF_USERNAME])
    await hass.async_add_executor_job(data.cleanup)

    return True


class UpCloud:
    """Handle all communication with the UpCloud API."""

    def __init__(
        self, hass: HomeAssistantType, manager: upcloud_api.CloudManager
    ) -> None:
        """Initialize the UpCloud connection."""
        self.hass = hass
        self.manager = manager
        self.data: Dict[str, upcloud_api.Server] = {}

    async def async_update(self, event_time):
        """Update data from UpCloud API."""
        _LOGGER.debug("Updating UpCloud data")
        servers = await self.hass.async_add_executor_job(self.manager.get_servers)
        self.data = {server.uuid: server for server in servers}


class UpCloudServerEntity(Entity):
    """Entity class for UpCloud servers."""

    def __init__(self, upcloud, uuid):
        """Initialize the UpCloud server entity."""
        self._upcloud = upcloud
        self.uuid = uuid
        self.data = None
        self._unsub_handlers = []

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return self.uuid

    @property
    def name(self):
        """Return the name of the component."""
        try:
            return DEFAULT_COMPONENT_NAME.format(self.data.title)
        except (AttributeError, KeyError, TypeError):
            return DEFAULT_COMPONENT_NAME.format(self.uuid)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._unsub_handlers.append(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_UPCLOUD, self._update_callback
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Invoke unsubscription handlers."""
        for unsub in self._unsub_handlers:
            unsub()
        self._unsub_handlers.clear()

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def icon(self):
        """Return the icon of this server."""
        return "mdi:server" if self.is_on else "mdi:server-off"

    @property
    def state(self):
        """Return state of the server."""
        try:
            return STATE_MAP.get(self.data.state)
        except AttributeError:
            return None

    @property
    def is_on(self):
        """Return true if the server is on."""
        return self.state == STATE_ON

    @property
    def device_class(self):
        """Return the class of this server."""
        return DEFAULT_COMPONENT_DEVICE_CLASS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the UpCloud server."""
        return {
            x: getattr(self.data, x, None)
            for x in (
                ATTR_UUID,
                ATTR_TITLE,
                ATTR_HOSTNAME,
                ATTR_ZONE,
                ATTR_STATE,
                ATTR_CORE_NUMBER,
                ATTR_MEMORY_AMOUNT,
            )
        }

    def update(self):
        """Update data of the UpCloud server."""
        self.data = self._upcloud.data.get(self.uuid)
