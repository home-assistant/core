"""Code to handle a Dynalite bridge."""
import asyncio
import pprint

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, area_registry as ar
from homeassistant.const import CONF_HOST

from .const import (
    DOMAIN,
    DATA_CONFIGS,
    LOGGER,
    CONF_AREACREATE,
    CONF_AREA_CREATE_MANUAL,
    CONF_AREA_CREATE_ASSIGN,
    CONF_AREA_CREATE_AUTO,
    ENTITY_CATEGORIES,
)
from dynalite_devices_lib import DynaliteDevices, DOMAIN as DYNDOMAIN
from dynalite_lib import CONF_ALL

from .light import DynaliteLight
from .switch import DynaliteSwitch
from .cover import DynaliteCover, DynaliteCoverWithTilt


class BridgeError(Exception):
    """Class to throw exceptions from DynaliteBridge."""

    def __init__(self, message):
        """Initialize the exception."""
        self.message = message


class DynaliteBridge:
    """Manages a single Dynalite bridge."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.area = {}
        self.async_add_entities = {}
        self.waiting_entities = {}
        self.all_entities = {}
        self.area_reg = None
        self.device_reg = None
        self.available = True

    @property
    def host(self):
        """Return the host of this bridge."""
        return self.config_entry.data[CONF_HOST]

    async def async_setup(self, tries=0):
        """Set up a Dynalite bridge based on host parameter."""
        host = self.host
        hass = self.hass
        self.area_reg = await ar.async_get_registry(hass)
        self.device_reg = await dr.async_get_registry(hass)
        LOGGER.debug(
            "component bridge async_setup - %s" % pprint.pformat(self.config_entry.data)
        )
        if host not in hass.data[DOMAIN][DATA_CONFIGS]:
            LOGGER.info("invalid host - %s" % host)
            return False

        self.config = hass.data[DOMAIN][DATA_CONFIGS][host]

        # Configure the dynalite devices
        self._dynalite_devices = DynaliteDevices(
            config=self.config,
            loop=hass.loop,
            newDeviceFunc=self.addDevices,
            updateDeviceFunc=self.updateDevice,
        )
        await self._dynalite_devices.async_setup()

        for category in ENTITY_CATEGORIES:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    self.config_entry, category
                )
            )

        return True

    @callback
    def addDevices(self, devices):
        """Call when devices should be added to home assistant."""
        added_entities = {}
        for category in ENTITY_CATEGORIES:
            added_entities[category] = []

        for device in devices:
            entity = None
            category = device.category
            if category == "light":
                entity = DynaliteLight(device, self)
            elif category == "switch":
                entity = DynaliteSwitch(device, self)
            elif category == "cover":
                if device.has_tilt:
                    entity = DynaliteCoverWithTilt(device, self)
                else:
                    entity = DynaliteCover(device, self)
            else:
                LOGGER.warning("Illegal device category %s", category)
                continue
            added_entities[category].append(entity)
            self.all_entities[entity.unique_id] = entity

        for category in ENTITY_CATEGORIES:
            if added_entities[category]:
                self.add_entities_when_registered(category, added_entities[category])

    @callback
    def updateDevice(self, device):
        """Call when a device or all devices should be updated."""
        if device == CONF_ALL:
            if self._dynalite_devices.available:
                LOGGER.info("Connected to dynalite host")
            else:
                LOGGER.info("Disconnected from dynalite host")
            for uid in self.all_entities:
                self.all_entities[uid].try_schedule_ha()
        else:
            uid = device.unique_id
            if uid in self.all_entities:
                self.all_entities[uid].try_schedule_ha()

    @callback
    def register_add_entities(self, category, async_add_entities):
        """Add an async_add_entities for a category."""
        self.async_add_entities[category] = async_add_entities
        if category in self.waiting_entities:
            self.async_add_entities[category](self.waiting_entities[category])

    def add_entities_when_registered(self, category, entities):
        """Add the entities to ha if async_add_entities was registered, otherwise queue until it is."""
        if not entities:
            return
        if category in self.async_add_entities:
            self.async_add_entities[category](entities)
        else:  # handle it later when it is registered
            if category not in self.waiting_entities:
                self.waiting_entities[category] = []
            self.waiting_entities[category].extend(entities)

    async def async_reset(self):
        """Reset this bridge to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        results = await asyncio.gather(
            self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, "light"
            ),
            self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, "switch"
            ),
            self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, "cover"
            ),
        )
        # None and True are OK
        return False not in results

    async def entity_added_to_ha(self, entity):
        """Call when an entity is added to HA so we can set its area."""
        areacreate = self.config[CONF_AREACREATE].lower()
        if areacreate == CONF_AREA_CREATE_MANUAL:
            LOGGER.debug("area assignment set to manual - ignoring")
            return  # only need to update the areas if it is 'assign' or 'create'
        if areacreate not in [CONF_AREA_CREATE_ASSIGN, CONF_AREA_CREATE_AUTO]:
            LOGGER.debug(
                CONF_AREACREATE
                + ' has unknown value of %s - assuming "'
                + CONF_AREA_CREATE_MANUAL
                + '" and ignoring',
                areacreate,
            )
            return
        uniqueID = entity.unique_id
        hassArea = entity.get_hass_area
        if hassArea != "":
            LOGGER.debug("assigning hass area %s to entity %s" % (hassArea, uniqueID))
            device = self.device_reg.async_get_device({(DYNDOMAIN, uniqueID)}, ())
            if not device:
                LOGGER.error("uniqueID %s has no device ID", uniqueID)
                return
            areaEntry = self.area_reg._async_is_registered(hassArea)
            if not areaEntry:
                if areacreate != CONF_AREA_CREATE_AUTO:
                    LOGGER.debug(
                        "Area %s not registered and "
                        + CONF_AREACREATE
                        + ' is not "'
                        + CONF_AREA_CREATE_AUTO
                        + '" - ignoring',
                        hassArea,
                    )
                    return
                else:
                    LOGGER.debug("Creating new area %s", hassArea)
                    areaEntry = self.area_reg.async_create(hassArea)
            LOGGER.debug("assigning deviceid=%s area_id=%s" % (device.id, areaEntry.id))
            self.device_reg.async_update_device(device.id, area_id=areaEntry.id)
