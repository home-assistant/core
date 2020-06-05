"""Support for Apple HomeKit."""
import asyncio
import ipaddress
import logging
import os

from aiohttp import web
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_MOTION,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    DEVICE_CLASS_BATTERY,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, Unauthorized
from homeassistant.helpers import device_registry, entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    BASE_FILTER_SCHEMA,
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    convert_filter,
)
from homeassistant.loader import async_get_integration
from homeassistant.util import get_local_ip

from .accessories import get_accessory
from .aidmanager import AccessoryAidStorage
from .const import (
    AID_STORAGE,
    ATTR_DISPLAY_NAME,
    ATTR_INTERGRATION,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    ATTR_VALUE,
    BRIDGE_NAME,
    BRIDGE_SERIAL_NUMBER,
    CONF_ADVERTISE_IP,
    CONF_AUTO_START,
    CONF_ENTITY_CONFIG,
    CONF_ENTRY_INDEX,
    CONF_FILTER,
    CONF_LINKED_BATTERY_CHARGING_SENSOR,
    CONF_LINKED_BATTERY_SENSOR,
    CONF_LINKED_MOTION_SENSOR,
    CONF_SAFE_MODE,
    CONF_ZEROCONF_DEFAULT_INTERFACE,
    CONFIG_OPTIONS,
    DEFAULT_AUTO_START,
    DEFAULT_PORT,
    DEFAULT_SAFE_MODE,
    DOMAIN,
    EVENT_HOMEKIT_CHANGED,
    HOMEKIT,
    HOMEKIT_PAIRING_QR,
    HOMEKIT_PAIRING_QR_SECRET,
    MANUFACTURER,
    SERVICE_HOMEKIT_RESET_ACCESSORY,
    SERVICE_HOMEKIT_START,
    SHUTDOWN_TIMEOUT,
    UNDO_UPDATE_LISTENER,
)
from .util import (
    dismiss_setup_message,
    get_persist_fullpath_for_entry_id,
    migrate_filesystem_state_data_for_primary_imported_entry_id,
    port_is_available,
    remove_state_files_for_entry_id,
    show_setup_message,
    validate_entity_config,
)

_LOGGER = logging.getLogger(__name__)

MAX_DEVICES = 150

# #### Driver Status ####
STATUS_READY = 0
STATUS_RUNNING = 1
STATUS_STOPPED = 2
STATUS_WAIT = 3


def _has_all_unique_names_and_ports(bridges):
    """Validate that each homekit bridge configured has a unique name."""
    names = [bridge[CONF_NAME] for bridge in bridges]
    ports = [bridge[CONF_PORT] for bridge in bridges]
    vol.Schema(vol.Unique())(names)
    vol.Schema(vol.Unique())(ports)
    return bridges


BRIDGE_SCHEMA = vol.All(
    cv.deprecated(CONF_ZEROCONF_DEFAULT_INTERFACE),
    vol.Schema(
        {
            vol.Optional(CONF_NAME, default=BRIDGE_NAME): vol.All(
                cv.string, vol.Length(min=3, max=25)
            ),
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_IP_ADDRESS): vol.All(ipaddress.ip_address, cv.string),
            vol.Optional(CONF_ADVERTISE_IP): vol.All(ipaddress.ip_address, cv.string),
            vol.Optional(CONF_AUTO_START, default=DEFAULT_AUTO_START): cv.boolean,
            vol.Optional(CONF_SAFE_MODE, default=DEFAULT_SAFE_MODE): cv.boolean,
            vol.Optional(CONF_FILTER, default={}): BASE_FILTER_SCHEMA,
            vol.Optional(CONF_ENTITY_CONFIG, default={}): validate_entity_config,
            vol.Optional(CONF_ZEROCONF_DEFAULT_INTERFACE): cv.boolean,
        },
        extra=vol.ALLOW_EXTRA,
    ),
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [BRIDGE_SCHEMA], _has_all_unique_names_and_ports)},
    extra=vol.ALLOW_EXTRA,
)


RESET_ACCESSORY_SERVICE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_ids}
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the HomeKit from yaml."""

    hass.data.setdefault(DOMAIN, {})

    _async_register_events_and_services(hass)

    if DOMAIN not in config:
        return True

    current_entries = hass.config_entries.async_entries(DOMAIN)

    entries_by_name = {entry.data[CONF_NAME]: entry for entry in current_entries}

    for index, conf in enumerate(config[DOMAIN]):
        bridge_name = conf[CONF_NAME]

        if (
            bridge_name in entries_by_name
            and entries_by_name[bridge_name].source == SOURCE_IMPORT
        ):
            entry = entries_by_name[bridge_name]
            # If they alter the yaml config we import the changes
            # since there currently is no practical way to support
            # all the options in the UI at this time.
            data = conf.copy()
            options = {}
            for key in CONFIG_OPTIONS:
                options[key] = data[key]
                del data[key]

            hass.config_entries.async_update_entry(entry, data=data, options=options)
            continue

        conf[CONF_ENTRY_INDEX] = index
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up HomeKit from a config entry."""
    _async_import_options_from_data_if_missing(hass, entry)

    conf = entry.data
    options = entry.options

    name = conf[CONF_NAME]
    port = conf[CONF_PORT]
    _LOGGER.debug("Begin setup HomeKit for %s", name)

    # If the previous instance hasn't cleaned up yet
    # we need to wait a bit
    if not await hass.async_add_executor_job(port_is_available, port):
        _LOGGER.warning("The local port %s is in use.", port)
        raise ConfigEntryNotReady

    if CONF_ENTRY_INDEX in conf and conf[CONF_ENTRY_INDEX] == 0:
        _LOGGER.debug("Migrating legacy HomeKit data for %s", name)
        hass.async_add_executor_job(
            migrate_filesystem_state_data_for_primary_imported_entry_id,
            hass,
            entry.entry_id,
        )

    aid_storage = AccessoryAidStorage(hass, entry.entry_id)

    await aid_storage.async_initialize()
    # ip_address and advertise_ip are yaml only
    ip_address = conf.get(CONF_IP_ADDRESS)
    advertise_ip = conf.get(CONF_ADVERTISE_IP)

    entity_config = options.get(CONF_ENTITY_CONFIG, {}).copy()
    auto_start = options.get(CONF_AUTO_START, DEFAULT_AUTO_START)
    safe_mode = options.get(CONF_SAFE_MODE, DEFAULT_SAFE_MODE)
    entity_filter = convert_filter(
        options.get(
            CONF_FILTER,
            {
                CONF_INCLUDE_DOMAINS: [],
                CONF_EXCLUDE_DOMAINS: [],
                CONF_INCLUDE_ENTITIES: [],
                CONF_EXCLUDE_ENTITIES: [],
            },
        )
    )

    homekit = HomeKit(
        hass,
        name,
        port,
        ip_address,
        entity_filter,
        entity_config,
        safe_mode,
        advertise_ip,
        entry.entry_id,
    )
    zeroconf_instance = await zeroconf.async_get_instance(hass)
    await hass.async_add_executor_job(homekit.setup, zeroconf_instance)

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        AID_STORAGE: aid_storage,
        HOMEKIT: homekit,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    if hass.state == CoreState.running:
        await homekit.async_start()
    elif auto_start:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, homekit.async_start)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    if entry.source == SOURCE_IMPORT:
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    dismiss_setup_message(hass, entry.entry_id)

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    homekit = hass.data[DOMAIN][entry.entry_id][HOMEKIT]

    if homekit.status == STATUS_RUNNING:
        await homekit.async_stop()

    for _ in range(0, SHUTDOWN_TIMEOUT):
        if not await hass.async_add_executor_job(
            port_is_available, entry.data[CONF_PORT]
        ):
            _LOGGER.info("Waiting for the HomeKit server to shutdown.")
            await asyncio.sleep(1)

    hass.data[DOMAIN].pop(entry.entry_id)

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Remove a config entry."""
    return await hass.async_add_executor_job(
        remove_state_files_for_entry_id, hass, entry.entry_id
    )


@callback
def _async_import_options_from_data_if_missing(hass: HomeAssistant, entry: ConfigEntry):
    options = dict(entry.options)
    data = dict(entry.data)
    modified = False
    for importable_option in CONFIG_OPTIONS:
        if importable_option not in entry.options and importable_option in entry.data:
            options[importable_option] = entry.data[importable_option]
            del data[importable_option]
            modified = True

    if modified:
        hass.config_entries.async_update_entry(entry, data=data, options=options)


@callback
def _async_register_events_and_services(hass: HomeAssistant):
    """Register events and services for HomeKit."""

    hass.http.register_view(HomeKitPairingQRView)

    def handle_homekit_reset_accessory(service):
        """Handle start HomeKit service call."""
        for entry_id in hass.data[DOMAIN]:
            if HOMEKIT not in hass.data[DOMAIN][entry_id]:
                continue
            homekit = hass.data[DOMAIN][entry_id][HOMEKIT]
            if homekit.status != STATUS_RUNNING:
                _LOGGER.warning(
                    "HomeKit is not running. Either it is waiting to be "
                    "started or has been stopped."
                )
                continue

            entity_ids = service.data.get("entity_id")
            homekit.reset_accessories(entity_ids)

    hass.services.async_register(
        DOMAIN,
        SERVICE_HOMEKIT_RESET_ACCESSORY,
        handle_homekit_reset_accessory,
        schema=RESET_ACCESSORY_SERVICE_SCHEMA,
    )

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        data = event.data
        entity_id = data.get(ATTR_ENTITY_ID)
        value = data.get(ATTR_VALUE)

        value_msg = f" to {value}" if value else ""
        message = f"send command {data[ATTR_SERVICE]}{value_msg} for {data[ATTR_DISPLAY_NAME]}"

        return {
            "name": "HomeKit",
            "message": message,
            "entity_id": entity_id,
        }

    hass.components.logbook.async_describe_event(
        DOMAIN, EVENT_HOMEKIT_CHANGED, async_describe_logbook_event
    )

    async def async_handle_homekit_service_start(service):
        """Handle start HomeKit service call."""
        for entry_id in hass.data[DOMAIN]:
            if HOMEKIT not in hass.data[DOMAIN][entry_id]:
                continue
            homekit = hass.data[DOMAIN][entry_id][HOMEKIT]
            if homekit.status != STATUS_READY:
                _LOGGER.warning(
                    "HomeKit is not ready. Either it is already running or has "
                    "been stopped."
                )
                continue
            await homekit.async_start()

    hass.services.async_register(
        DOMAIN, SERVICE_HOMEKIT_START, async_handle_homekit_service_start
    )


class HomeKit:
    """Class to handle all actions between HomeKit and Home Assistant."""

    def __init__(
        self,
        hass,
        name,
        port,
        ip_address,
        entity_filter,
        entity_config,
        safe_mode,
        advertise_ip=None,
        entry_id=None,
    ):
        """Initialize a HomeKit object."""
        self.hass = hass
        self._name = name
        self._port = port
        self._ip_address = ip_address
        self._filter = entity_filter
        self._config = entity_config
        self._safe_mode = safe_mode
        self._advertise_ip = advertise_ip
        self._entry_id = entry_id
        self.status = STATUS_READY

        self.bridge = None
        self.driver = None

    def setup(self, zeroconf_instance):
        """Set up bridge and accessory driver."""
        # pylint: disable=import-outside-toplevel
        from .accessories import HomeBridge, HomeDriver

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        ip_addr = self._ip_address or get_local_ip()
        persist_file = get_persist_fullpath_for_entry_id(self.hass, self._entry_id)

        self.driver = HomeDriver(
            self.hass,
            self._entry_id,
            self._name,
            address=ip_addr,
            port=self._port,
            persist_file=persist_file,
            advertised_address=self._advertise_ip,
            zeroconf_instance=zeroconf_instance,
        )

        # If we do not load the mac address will be wrong
        # as pyhap uses a random one until state is restored
        if os.path.exists(persist_file):
            self.driver.load()
        else:
            self.driver.persist()

        self.bridge = HomeBridge(self.hass, self.driver, self._name)
        if self._safe_mode:
            _LOGGER.debug("Safe_mode selected for %s", self._name)
            self.driver.safe_mode = True

    def reset_accessories(self, entity_ids):
        """Reset the accessory to load the latest configuration."""
        aid_storage = self.hass.data[DOMAIN][self._entry_id][AID_STORAGE]
        removed = []
        for entity_id in entity_ids:
            aid = aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
            if aid not in self.bridge.accessories:
                _LOGGER.warning(
                    "Could not reset accessory. entity_id not found %s", entity_id
                )
                continue
            acc = self.remove_bridge_accessory(aid)
            removed.append(acc)
        self.driver.config_changed()

        for acc in removed:
            self.bridge.add_accessory(acc)
        self.driver.config_changed()

    def add_bridge_accessory(self, state):
        """Try adding accessory to bridge if configured beforehand."""
        if not self._filter(state.entity_id):
            return

        # The bridge itself counts as an accessory
        if len(self.bridge.accessories) + 1 >= MAX_DEVICES:
            _LOGGER.warning(
                "Cannot add %s as this would exceeded the %d device limit. Consider using the filter option.",
                state.entity_id,
                MAX_DEVICES,
            )
            return

        aid = self.hass.data[DOMAIN][self._entry_id][
            AID_STORAGE
        ].get_or_allocate_aid_for_entity_id(state.entity_id)
        conf = self._config.pop(state.entity_id, {})
        # If an accessory cannot be created or added due to an exception
        # of any kind (usually in pyhap) it should not prevent
        # the rest of the accessories from being created
        try:
            acc = get_accessory(self.hass, self.driver, state, aid, conf)
            if acc is not None:
                self.bridge.add_accessory(acc)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Failed to create a HomeKit accessory for %s", state.entity_id
            )

    def remove_bridge_accessory(self, aid):
        """Try adding accessory to bridge if configured beforehand."""
        acc = None
        if aid in self.bridge.accessories:
            acc = self.bridge.accessories.pop(aid)
        return acc

    async def async_start(self, *args):
        """Start the accessory driver."""

        if self.status != STATUS_READY:
            return
        self.status = STATUS_WAIT

        ent_reg = await entity_registry.async_get_registry(self.hass)
        dev_reg = await device_registry.async_get_registry(self.hass)

        device_lookup = ent_reg.async_get_device_class_lookup(
            {
                (BINARY_SENSOR_DOMAIN, DEVICE_CLASS_BATTERY_CHARGING),
                (BINARY_SENSOR_DOMAIN, DEVICE_CLASS_MOTION),
                (SENSOR_DOMAIN, DEVICE_CLASS_BATTERY),
            }
        )

        bridged_states = []
        for state in self.hass.states.async_all():
            if not self._filter(state.entity_id):
                continue

            ent_reg_ent = ent_reg.async_get(state.entity_id)
            if ent_reg_ent:
                await self._async_set_device_info_attributes(
                    ent_reg_ent, dev_reg, state.entity_id
                )
                self._async_configure_linked_sensors(ent_reg_ent, device_lookup, state)

            bridged_states.append(state)

        self._async_register_bridge(dev_reg)
        await self.hass.async_add_executor_job(self._start, bridged_states)

    @callback
    def _async_register_bridge(self, dev_reg):
        """Register the bridge as a device so homekit_controller and exclude it from discovery."""
        formatted_mac = device_registry.format_mac(self.driver.state.mac)
        # Connections and identifiers are both used here.
        #
        # connections exists so homekit_controller can know the
        # virtual mac address of the bridge and know to not offer
        # it via discovery.
        #
        # identifiers is used as well since the virtual mac may change
        # because it will not survive manual pairing resets (deleting state file)
        # which we have trained users to do over the past few years
        # because this was the way you had to fix homekit when pairing
        # failed.
        #
        connection = (device_registry.CONNECTION_NETWORK_MAC, formatted_mac)
        identifier = (DOMAIN, self._entry_id, BRIDGE_SERIAL_NUMBER)
        self._async_purge_old_bridges(dev_reg, identifier, connection)
        dev_reg.async_get_or_create(
            config_entry_id=self._entry_id,
            identifiers={identifier},
            connections={connection},
            manufacturer=MANUFACTURER,
            name=self._name,
            model="Home Assistant HomeKit Bridge",
        )

    @callback
    def _async_purge_old_bridges(self, dev_reg, identifier, connection):
        """Purge bridges that exist from failed pairing or manual resets."""
        devices_to_purge = []
        for entry in dev_reg.devices.values():
            if self._entry_id in entry.config_entries and (
                identifier not in entry.identifiers
                or connection not in entry.connections
            ):
                devices_to_purge.append(entry.id)

        for device_id in devices_to_purge:
            dev_reg.async_remove_device(device_id)

    def _start(self, bridged_states):
        from . import (  # noqa: F401 pylint: disable=unused-import, import-outside-toplevel
            type_cameras,
            type_covers,
            type_fans,
            type_lights,
            type_locks,
            type_media_players,
            type_security_systems,
            type_sensors,
            type_switches,
            type_thermostats,
        )

        for state in bridged_states:
            self.add_bridge_accessory(state)

        self.driver.add_accessory(self.bridge)

        if not self.driver.state.paired:
            show_setup_message(
                self.hass,
                self._entry_id,
                self._name,
                self.driver.state.pincode,
                self.bridge.xhm_uri(),
            )

        _LOGGER.debug("Driver start for %s", self._name)
        self.hass.add_job(self.driver.start)
        self.status = STATUS_RUNNING

    async def async_stop(self, *args):
        """Stop the accessory driver."""
        if self.status != STATUS_RUNNING:
            return
        self.status = STATUS_STOPPED
        _LOGGER.debug("Driver stop for %s", self._name)
        self.hass.add_job(self.driver.stop)

    @callback
    def _async_configure_linked_sensors(self, ent_reg_ent, device_lookup, state):
        if (
            ent_reg_ent is None
            or ent_reg_ent.device_id is None
            or ent_reg_ent.device_id not in device_lookup
            or ent_reg_ent.device_class
            in (DEVICE_CLASS_BATTERY_CHARGING, DEVICE_CLASS_BATTERY)
        ):
            return

        if ATTR_BATTERY_CHARGING not in state.attributes:
            battery_charging_binary_sensor_entity_id = device_lookup[
                ent_reg_ent.device_id
            ].get((BINARY_SENSOR_DOMAIN, DEVICE_CLASS_BATTERY_CHARGING))
            if battery_charging_binary_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_BATTERY_CHARGING_SENSOR,
                    battery_charging_binary_sensor_entity_id,
                )

        if ATTR_BATTERY_LEVEL not in state.attributes:
            battery_sensor_entity_id = device_lookup[ent_reg_ent.device_id].get(
                (SENSOR_DOMAIN, DEVICE_CLASS_BATTERY)
            )
            if battery_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_BATTERY_SENSOR, battery_sensor_entity_id
                )

        if state.entity_id.startswith(f"{CAMERA_DOMAIN}."):
            motion_binary_sensor_entity_id = device_lookup[ent_reg_ent.device_id].get(
                (BINARY_SENSOR_DOMAIN, DEVICE_CLASS_MOTION)
            )
            if motion_binary_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_MOTION_SENSOR, motion_binary_sensor_entity_id,
                )

    async def _async_set_device_info_attributes(self, ent_reg_ent, dev_reg, entity_id):
        """Set attributes that will be used for homekit device info."""
        ent_cfg = self._config.setdefault(entity_id, {})
        if ent_reg_ent.device_id:
            dev_reg_ent = dev_reg.async_get(ent_reg_ent.device_id)
            if dev_reg_ent is not None:
                # Handle missing devices
                if dev_reg_ent.manufacturer:
                    ent_cfg[ATTR_MANUFACTURER] = dev_reg_ent.manufacturer
                if dev_reg_ent.model:
                    ent_cfg[ATTR_MODEL] = dev_reg_ent.model
                if dev_reg_ent.sw_version:
                    ent_cfg[ATTR_SOFTWARE_VERSION] = dev_reg_ent.sw_version
        if ATTR_MANUFACTURER not in ent_cfg:
            integration = await async_get_integration(self.hass, ent_reg_ent.platform)
            ent_cfg[ATTR_INTERGRATION] = integration.name


class HomeKitPairingQRView(HomeAssistantView):
    """Display the homekit pairing code at a protected url."""

    url = "/api/homekit/pairingqr"
    name = "api:homekit:pairingqr"
    requires_auth = False

    # pylint: disable=no-self-use
    async def get(self, request):
        """Retrieve the pairing QRCode image."""
        if not request.query_string:
            raise Unauthorized()
        entry_id, secret = request.query_string.split("-")

        if (
            entry_id not in request.app["hass"].data[DOMAIN]
            or secret
            != request.app["hass"].data[DOMAIN][entry_id][HOMEKIT_PAIRING_QR_SECRET]
        ):
            raise Unauthorized()
        return web.Response(
            body=request.app["hass"].data[DOMAIN][entry_id][HOMEKIT_PAIRING_QR],
            content_type="image/svg+xml",
        )
