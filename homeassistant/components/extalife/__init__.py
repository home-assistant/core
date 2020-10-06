"""Support for ExtaLife devices."""
import asyncio
from datetime import timedelta
import importlib
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as DOMAIN_BINARY_SENSOR
from homeassistant.components.climate import DOMAIN as DOMAIN_CLIMATE
from homeassistant.components.cover import DOMAIN as DOMAIN_COVER
from homeassistant.components.light import DOMAIN as DOMAIN_LIGHT
from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    device_registry as dr,
    entity_component,
    entity_platform,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .config_flow import get_default_options
from .helpers.const import (
    CONF_CONTROLLER_IP,
    CONF_OPTIONS,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_USER,
    DATA_CORE,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    DOMAIN_TRANSMITTER,
    OPTIONS_COVER,
    OPTIONS_COVER_INV_CONTROL,
    OPTIONS_COVER_INVERTED_CONTROL,
    OPTIONS_GENERAL,
    OPTIONS_GENERAL_DISABLE_NOT_RESPONDING,
    OPTIONS_GENERAL_POLL_INTERVAL,
    OPTIONS_LIGHT,
    OPTIONS_LIGHT_ICONS_LIST,
    OPTIONS_SWITCH,
    SIGNAL_DATA_UPDATED,
    SIGNAL_NOTIF_STATE_UPDATED,
)
from .helpers.core import Core
from .helpers.services import ExtaLifeServices
from .pyextalife import (
    DEVICE_ARR_ALL_CLIMATE,
    DEVICE_ARR_ALL_COVER,
    DEVICE_ARR_ALL_IGNORE,
    DEVICE_ARR_ALL_LIGHT,
    DEVICE_ARR_ALL_SENSOR,
    DEVICE_ARR_ALL_SENSOR_BINARY,
    DEVICE_ARR_ALL_SENSOR_MEAS,
    DEVICE_ARR_ALL_SENSOR_MULTI,
    DEVICE_ARR_ALL_SWITCH,
    DEVICE_ARR_ALL_TRANSMITTER,
    DEVICE_ARR_EXTA_FREE_RECEIVER,
    DEVICE_ICON_ARR_LIGHT,
    DEVICE_MAP_TYPE_TO_MODEL,
    PRODUCT_CONTROLLER_MODEL,
    PRODUCT_MANUFACTURER,
    PRODUCT_SERIES,
    PRODUCT_SERIES_EXTA_FREE,
    ExtaLifeAPI,
    TCPConnError,
)

_LOGGER = logging.getLogger(__name__)

OPTIONS_DEFAULTS = get_default_options()

# schema validations
OPTIONS_CONF_SCHEMA = {
    vol.Optional(OPTIONS_GENERAL, default=OPTIONS_DEFAULTS[OPTIONS_GENERAL]): {
        vol.Optional(
            OPTIONS_GENERAL_POLL_INTERVAL,
            default=OPTIONS_DEFAULTS[OPTIONS_GENERAL][OPTIONS_GENERAL_POLL_INTERVAL],
        ): cv.positive_int,
    },
    vol.Optional(OPTIONS_LIGHT, default=OPTIONS_DEFAULTS[OPTIONS_LIGHT]): {
        vol.Optional(
            OPTIONS_LIGHT_ICONS_LIST,
            default=OPTIONS_DEFAULTS[OPTIONS_LIGHT][OPTIONS_LIGHT_ICONS_LIST],
        ): cv.ensure_list,
    },
    vol.Optional(OPTIONS_COVER, default=OPTIONS_DEFAULTS[OPTIONS_COVER]): {
        vol.Optional(
            OPTIONS_COVER_INV_CONTROL,
            default=OPTIONS_DEFAULTS[OPTIONS_COVER][OPTIONS_COVER_INVERTED_CONTROL],
        ): cv.boolean,
    },
}

# configuration.yaml config schema for HA validations
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_CONTROLLER_IP, default=""): cv.string,
                vol.Required(CONF_USER): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                ): cv.positive_int,
                vol.Optional(
                    CONF_OPTIONS, default=get_default_options()
                ): OPTIONS_CONF_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    #  Flatten configuration but keep old data if user rollbacks HASS
    if config_entry.version == 1:

        options = {**config_entry.options}
        options.setdefault(
            OPTIONS_GENERAL,
            {
                OPTIONS_GENERAL_POLL_INTERVAL: config_entry.data.get(
                    CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                )
            },
        )
        config_entry.options = {**options}

        new = {**config_entry.data}
        try:
            new.pop(CONF_POLL_INTERVAL)
            new.pop(
                CONF_OPTIONS
            )  # get rid of errorneously migrated options from integration 1.0
        except:
            pass
        config_entry.data = {**new}

        config_entry.version = 2

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_setup(hass: HomeAssistantType, hass_config: ConfigType):
    """Set up Exta Life component from configuration.yaml. This will basically
    forward the config to a Config Flow and will migrate to Config Entry"""

    _LOGGER.debug("hass_config: %s", hass_config)

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in hass_config:

        hass.data.setdefault(
            DOMAIN, {CONF_OPTIONS: hass_config[DOMAIN].get(CONF_OPTIONS, None)}
        )
        _LOGGER.debug("async_setup, hass.data.domain: %s", hass.data.get(DOMAIN))

        result = hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=hass_config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Set up Exta Life component from a Config Entry"""

    _LOGGER.debug("Inside async_setup_entry. %s", config_entry.data)

    hass.data.setdefault(DOMAIN, {})
    Core.create(hass, config_entry)
    return await initialize(hass, config_entry)


async def async_unload_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Unload a config entry: unload platform entities, stored data, deregister signal listeners"""
    core = Core.get(config_entry.entry_id)

    await core.unload_entry_from_hass()

    return True


async def initialize(hass: HomeAssistantType, config_entry: ConfigEntry):
    """ Initialize Exta Life integration based on a Config Entry """

    def init_options(hass: HomeAssistantType, config_entry: ConfigEntry):
        """Populate default options for Exta Life."""
        default = get_default_options()
        options = {**config_entry.options}
        # migrate options after creation of ConfigEntry
        if not options:
            yaml_conf = hass.data.get(DOMAIN)
            yaml_options = None
            if yaml_conf is not None:
                yaml_options = yaml_conf.get(CONF_OPTIONS)

            _LOGGER.debug("init_options, yaml_options %s", yaml_options)

            options = default if yaml_options is None else yaml_options

        # set default values if something is missing
        options_def = options.copy()
        for k, v in default.items():
            options_def.setdefault(k, v)

        # check for changes and if options should be peristed
        if options_def != options or not config_entry.options:
            hass.config_entries.async_update_entry(config_entry, options=options_def)

    async def api_connect(user, password, host):
        controller = Core.get(config_entry.entry_id).api
        await controller.async_connect(user, password, host=host)
        return controller

    init_options(hass, config_entry)

    controller = None

    el_conf = config_entry.data
    core = Core.get(config_entry.entry_id)

    data = core.data_manager

    controller_ip = el_conf[CONF_CONTROLLER_IP]  # will be known after config flow

    try:
        _LOGGER.info("ExtaLife initializing...")
        if controller_ip is not None:
            _LOGGER.debug("Trying to connect to controller using IP: %s", controller_ip)
        else:
            _LOGGER.info("No controller IP specified. Trying autodiscovery")

        # get instance: this will already try to connect and logon
        try:
            controller = await api_connect(
                el_conf[CONF_USER], el_conf[CONF_PASSWORD], controller_ip
            )
        except TCPConnError as e:
            _LOGGER.debug(
                "Connection exception: %s, class: %s", e.previous, e.previous.__class__
            )
            # invalid IP / IP changed? - try autodetection
            if isinstance(e.previous, OSError) and e.previous.errno == 113:
                _LOGGER.warning(
                    "Could not connect to EFC-01 on IP stored in configuration: %s. Trying to discover controller IP in the network",
                    controller_ip,
                )
                # controller = await hass.async_add_executor_job(api_connect, el_conf[CONF_USER], el_conf[CONF_PASSWORD], None)
                controller = await api_connect(
                    el_conf[CONF_USER], el_conf[CONF_PASSWORD], None
                )

                # update ConfigEntry with new IP
                cur_data = {**config_entry.data}
                cur_data.update({CONF_CONTROLLER_IP: controller.host})
                hass.config_entries.async_update_entry(config_entry, data=cur_data)
                _LOGGER.info("Controller IP updated to: %s", controller.host)
            else:
                raise e
        _LOGGER.debug("Connected to controller on IP: %s", controller.host)

        sw_version = controller.sw_version

        if sw_version is not None:
            _LOGGER.info("EFC-01 Software version: %s", sw_version)
        else:
            _LOGGER.error(
                "Error communicating with the EFC-01 controller. Return data %s",
                sw_version,
            )

            return False

    except TCPConnError as e:
        host = controller.host if (controller and controller.host) else "unknown"
        _LOGGER.error("Could not connect to EFC-01 on IP: %s", host)

        await core.unload_entry_from_hass()
        raise ConfigEntryNotReady

    await core.register_controller()

    core = Core.get(config_entry.entry_id)

    await data.async_start_polling(poll_now=True)

    # publish services to HA service registry
    await core.async_register_services()

    _LOGGER.info("Exta Life integration setup successfully!")
    return True


class ChannelDataManager:
    """Get the latest data from EFC-01, call device discovery, handle status notifications."""

    def __init__(self, hass: HomeAssistantType, config_entry: ConfigEntry):
        """Initialize the data object."""
        self.data = None
        self._hass = hass
        self._config_entry = config_entry
        self._listeners = []

        self.channels_indx = {}
        self.initial_channels = {}

        # self._notif_listener: NotifThreadListener = None

        self._poller_callback_remove = None
        self._ping_callback_remove = None

    @property
    def core(self):
        return Core.get(self._config_entry.entry_id)

    @property
    def controller(self) -> ExtaLifeAPI:
        return Core.get(self._config_entry.entry_id).api

    # callback
    def on_notify(self, msg):
        _LOGGER.debug("Received status change notification from controller: %s", msg)
        data = msg.get("data")
        channel = data.get("channel", "#")
        chan_id = str(data.get("id")) + "-" + str(channel)

        # inform HA entity of state change via notification
        signal = ExtaLifeChannel.get_notif_upd_signal(chan_id)
        if channel != "#":
            self.core.async_signal_send(signal, data)
        else:
            self.core.async_signal_send_sync(signal, data)

    def update_channel(self, id: str, data: dict):
        """Update data of a channel e.g. after notification data received and processed
        by an entity"""
        self.channels_indx.update({id: data})

    async def async_start_polling(self, poll_now: bool):
        """Start cyclic status polling

        poll_now - fetch devices' status immediately and don't wait for the nearest poll"""

        if poll_now:
            await self.async_execute_status_polling()

    async def async_execute_status_polling(self):
        """ Executes status polling triggered externally, not via periodic callback + resets next poll time """
        if self._poller_callback_remove is not None:
            self._poller_callback_remove()

        await self._async_update_callback()

        self.setup_periodic_callback()

    async def async_stop_polling(self):
        """ Turn off periodic callbacks for status update """

        if self._poller_callback_remove is not None:
            self._poller_callback_remove()
            self._poller_callback_remove = None

    async def _async_update_callback(self, now=None):
        """Get the latest device&channel status data from EFC-01.
        This method is called from HA task scheduler via async_track_time_interval"""

        _LOGGER.debug("Executing EFC-01 status polling....")
        # use Exta Life TCP communication class

        # if connection error or other - will receive None
        # otherwise it contains a list of channels
        channels = await self.controller.async_get_channels()

        if channels is None:
            _LOGGER.warning("No Channels could be obtained from the controller")
            return

        # create indexed access: dict from list element
        # dict key = "data" section
        for elem in channels:
            chan = {elem["id"]: elem["data"]}
            self.channels_indx.update(chan)

        self.core.async_signal_send(SIGNAL_DATA_UPDATED)

        _LOGGER.debug(
            "Exta Life: status for %s devices updated", len(self.channels_indx)
        )

        self.discover_devices()

        if now is None:
            # store initial channel list for subsequent discovery runs for detection of new devices
            # store only for the 1st call (by setup code, not by HA)
            self.initial_channels = self.channels_indx.copy()

    def setup_periodic_callback(self):
        """ (Re)set periodic callback period based on options """

        # register callback for periodic status update polling + device discovery
        interval = self._config_entry.options.get(OPTIONS_GENERAL).get(
            OPTIONS_GENERAL_POLL_INTERVAL
        )

        _LOGGER.debug("setup_periodic_callback(). Setting interval: %s", interval)

        self._poller_callback_remove = self.core.async_track_time_interval(
            self._async_update_callback, timedelta(minutes=interval)
        )

    def discover_devices(self):
        """
        Fetch / refresh device data & discover devices and register them in Home Assistant.
        """

        component_configs = {}
        other_configs = {}

        # get data from the ChannelDataManager object stored in HA object data

        entities = 0
        for channel_id, channel_data in self.channels_indx.items():  # -> dict id:data
            channel = {"id": channel_id, "data": channel_data}

            chn_type = channel["data"]["type"]

            # do discovery only for newly discovered devices
            ch_id = channel.get("id")
            if self.initial_channels.get(ch_id):
                continue

            component_name = None

            # skip some devices that are not to be shown nor controlled by HA
            if chn_type in DEVICE_ARR_ALL_IGNORE:
                continue

            if chn_type in DEVICE_ARR_ALL_SWITCH:
                icon = channel["data"]["icon"]
                if icon in self._config_entry.options.get(DOMAIN_LIGHT).get(
                    OPTIONS_LIGHT_ICONS_LIST
                ):
                    component_name = DOMAIN_LIGHT
                else:
                    component_name = DOMAIN_SWITCH

            elif chn_type in DEVICE_ARR_ALL_LIGHT:
                component_name = DOMAIN_LIGHT

            elif chn_type in DEVICE_ARR_ALL_COVER:
                component_name = DOMAIN_COVER

            elif chn_type in DEVICE_ARR_ALL_SENSOR_MEAS:
                component_name = DOMAIN_SENSOR

            elif chn_type in DEVICE_ARR_ALL_SENSOR_BINARY:
                component_name = DOMAIN_BINARY_SENSOR

            elif chn_type in DEVICE_ARR_ALL_SENSOR_MULTI:
                component_name = DOMAIN_SENSOR

            elif chn_type in DEVICE_ARR_ALL_CLIMATE:
                component_name = DOMAIN_CLIMATE

            elif chn_type in DEVICE_ARR_ALL_TRANSMITTER:
                other_configs.setdefault(DOMAIN_TRANSMITTER, []).append(channel)
                continue

            if component_name is None:
                _LOGGER.warning(
                    "Unsupported device type: %s, channel id: %s",
                    chn_type,
                    channel["id"],
                )
                continue

            component_configs.setdefault(component_name, []).append(channel)
            entities += 1

        _LOGGER.debug("Exta Life devices found during discovery: %s", entities)

        # Load discovered devices
        for component_name, channels in component_configs.items():
            # store array of channels (variable 'channels') for each platform
            self.core.push_channels(component_name, channels)
            self._hass.async_create_task(
                self._hass.config_entries.async_forward_entry_setup(
                    self._config_entry, component_name
                )
            )

        # setup pseudo-platforms
        for component_name, channels in other_configs.items():
            # store array of channels (variable 'channels') for each platform
            self.core.push_channels(component_name, channels, True)
            self._hass.async_create_task(
                self.core.async_setup_custom_platforms(component_name)
            )


class ExtaLifeChannel(Entity):
    """Base class of a ExtaLife Channel (an equivalent of HA's Entity)."""

    # _cmd_in_execution = False

    def __init__(self, channel_data, config_entry: ConfigEntry):
        """Channel data -- channel information from PyExtaLife."""
        # e.g. channel_data = { "id": "0-1", "data": {TCP attributes}}
        self.channel_data = channel_data.get("data")
        self.channel_id = channel_data.get("id")
        self.data_available = True
        self.config_entry = config_entry

        self._signal_data_updated = None
        self._signal_data_notif_upd = None

    @staticmethod
    def get_notif_upd_signal(ch_id):
        return f"{SIGNAL_NOTIF_STATE_UPDATED}_{ch_id}"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        _LOGGER.debug("async_added_to_hass() for entity: %s", self.entity_id)
        Core.get(self.config_entry.entry_id).async_signal_register(
            SIGNAL_DATA_UPDATED, self.async_update_callback
        )

        Core.get(self.config_entry.entry_id).async_signal_register(
            self.get_notif_upd_signal(self.channel_id),
            self.async_state_notif_update_callback,
        )

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()

    async def async_update_callback(self):
        """ Inform HA of state update from status poller"""
        _LOGGER.debug("Update callback for entty id: %s", self.entity_id)
        self.async_schedule_update_ha_state(True)

    async def async_state_notif_update_callback(self, *args):
        """ Inform HA of state change received from controller status notification """
        data = args[0]
        _LOGGER.debug(
            "State update notification callback for entity id: %s, data: %s",
            self.entity_id,
            data,
        )

        self.on_state_notification(data)

    def on_state_notification(self, data):
        """ must be overriden in entity subclasses """
        pass

    def get_unique_id(self):
        """ Provide unique id for HA entity registry """
        return f"extalife-{str(self.channel_data.get('serial'))}-{self.channel_id}"

    @property
    def should_poll(self):
        """
        Turn off HA polling in favour of update-when-needed status changes.
        Updates will be passed to HA by calling async_schedule_update_ha_state() for each entity
        """
        return False

    @property
    def core(self):
        return Core.get(self.config_entry.entry_id)

    @property
    def controller(self) -> ExtaLifeAPI:
        """Return PyExtaLife's controller component associated with entity."""
        return self.core.api

    @property
    def data_poller(self) -> ChannelDataManager:
        """Return Data poller object"""
        return self.core.data_manager

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.get_unique_id()

    @property
    def model(self) -> str:
        """ Return model """
        return DEVICE_MAP_TYPE_TO_MODEL.get(self.channel_data.get("type"))

    @property
    def is_exta_free(self) -> bool:
        """ Returns boolean if entity represents Exta Free device """
        return self.channel_data.get("exta_free_device")

    @property
    def assumed_state(self) -> bool:
        """ Returns boolean if entity status is assumed status """
        ret = self.is_exta_free
        _LOGGER.debug("Assumed state for entity: %s, %s", self.entity_id, ret)
        return ret

    @property
    def device_info(self):
        prod_series = (
            PRODUCT_SERIES if not self.is_exta_free else PRODUCT_SERIES_EXTA_FREE
        )
        return {
            "identifiers": {(DOMAIN, self.channel_data.get("serial"))},
            "name": f"{PRODUCT_MANUFACTURER} {prod_series} {self.model}",
            "manufacturer": PRODUCT_MANUFACTURER,
            "model": self.model,
            "via_device": (DOMAIN, self.controller.mac),
        }

    @property
    def name(self) -> Optional[str]:
        """Return name of the entity"""
        return self.channel_data["alias"]

    async def async_action(self, action, **add_pars):
        """
        Run controller command/action.

        Actions are currently hardcoded in platforms
        """

        _LOGGER.debug(
            "Executing action %s on channel %s, params: %s",
            action,
            self.channel_id,
            add_pars,
        )

        try:
            resp = await self.controller.async_execute_action(
                action, self.channel_id, **add_pars
            )
        except TCPConnError as err:
            _LOGGER.error(err.data)

        return resp

    @property
    def available(self):
        is_timeout = (
            self.channel_data.get("is_timeout")
            if self.config_entry.options.get(OPTIONS_GENERAL_DISABLE_NOT_RESPONDING)
            else False
        )
        _LOGGER.debug(
            "available() for entity: %s. self.data_available: %s; 'is_timeout': %s",
            self.entity_id,
            self.data_available,
            is_timeout,
        )

        return self.data_available == True and is_timeout == False

    async def async_update(self):
        """Call to update state."""
        # data poller object contains PyExtaLife API channel data dict value pair: {("id"): ("data")}
        channel_indx = self.data_poller.channels_indx

        # read "data" section/dict by channel id
        data = channel_indx.get(self.channel_id)

        _LOGGER.debug(
            "async_update() for entity: %s, data to be updated: %s",
            self.entity_id,
            data,
        )

        if data is None:
            self.data_available = False
            return

        self.data_available = True
        self.channel_data = data

    def sync_data_update_ha(self):
        """Performs update of Data Manager data with Entity data and calls HA state update.
        This is useful e.g. when Entity receives notification update, processes it and
        then must update its state. For consistency reasons - Data Manager is updated and then
        HA status update is scheduled"""

        self.data_poller.update_channel(self.channel_id, self.channel_data)
        self.async_schedule_update_ha_state(True)

    @property
    def device_state_attributes(self):
        """" Return state atributes """
        return {
            "channel_id": self.channel_id,
            "not_responding": self.channel_data.get("is_timeout"),
        }


class ExtaLifeController(Entity):
    """Base class of a ExtaLife Channel (an equivalent of HA's Entity)."""

    def __init__(self, entry_id):
        self._entry_id = entry_id
        self._core = Core.get(entry_id)

    @staticmethod
    async def register_controller(entry_id):
        """Create Controller entity and create device for it in Dev. Registry

        entry_id - Config Entry entry_id"""

        core = Core.get(entry_id)
        from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL

        platform = entity_platform.EntityPlatform(
            hass=core.get_hass(),
            logger=_LOGGER,
            platform_name=DOMAIN,
            domain=DOMAIN,
            platform=None,
            entity_namespace=None,
            scan_interval=DEFAULT_SCAN_INTERVAL,
        )
        platform.config_entry = core.config_entry
        await platform.async_add_entities(
            [ExtaLifeController(core.config_entry.entry_id)]
        )

    async def async_added_to_hass(self):
        """ When entity added to HA """

        # let the Core know about the controller entity
        self._core.controller_entity_added_to_hass(self)

    @property
    def unique_id(self):
        return self.mac

    @property
    def mac(self):
        """ controller's MAC address """
        return self.api.mac

    @property
    def icon(self):
        return "mdi:cube-outline"

    @property
    def should_poll(self):
        """ Turn off HA status polling """
        return False

    @property
    def core(self):
        return Core.get(self._entry_id)

    @property
    def api(self) -> ExtaLifeAPI:
        """Return PyExtaLife's controller API instance."""
        return self.core.api

    @property
    def device_info(self):
        """ Register controller in Device Registry """
        return {
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.mac)},
            "identifiers": {(DOMAIN, self.mac)},
            "manufacturer": PRODUCT_MANUFACTURER,
            "name": f"{PRODUCT_MANUFACTURER} {PRODUCT_SERIES} {PRODUCT_CONTROLLER_MODEL}",
            "model": PRODUCT_CONTROLLER_MODEL,
        }

    @property
    def name(self) -> Optional[str]:
        """Return name of the entity"""
        return self.api.name

    @property
    def config_entry(self):
        return self.core.config_entry

    @property
    def available(self):
        """ Entity available? """
        # for lost api connection this should return False, so entity status changes to 'unavailable'
        return self.api.is_connected

    @property
    def state(self) -> str:
        """Return the controller state. it will be either 'ready' or 'unavailable' """
        return "ready"

    @property
    def device_state_attributes(self):
        return {
            "type": "gateway",
            "mac_address": self.mac,
            "ipv4_addres:": self.api.host,
            "software_version": self.api.sw_version,
            "name": self.api.name,
        }

    async def async_update(self):
        """ Entity update callback """
        # not necessary for the controller entity; will be updated on demand, externally
        pass
