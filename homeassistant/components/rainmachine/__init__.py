"""Support for RainMachine devices."""
import asyncio

from regenmaschine import Client
from regenmaschine.errors import RainMachineError
import voluptuous as vol

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.service import verify_domain_control
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ZONE_RUN_TIME,
    DATA_CONTROLLER,
    DATA_COORDINATOR,
    DATA_PROGRAMS,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_CURRENT,
    DATA_RESTRICTIONS_UNIVERSAL,
    DATA_ZONES,
    DEFAULT_ZONE_RUN,
    DOMAIN,
    LOGGER,
)
from .coordinator import RainMachineCoordinator

CONF_PROGRAM_ID = "program_id"
CONF_SECONDS = "seconds"
CONF_ZONE_ID = "zone_id"

DEFAULT_ATTRIBUTION = "Data provided by Green Electronics LLC"
DEFAULT_ICON = "mdi:water"
DEFAULT_SSL = True

SERVICE_ALTER_PROGRAM = vol.Schema({vol.Required(CONF_PROGRAM_ID): cv.positive_int})

SERVICE_ALTER_ZONE = vol.Schema({vol.Required(CONF_ZONE_ID): cv.positive_int})

SERVICE_PAUSE_WATERING = vol.Schema({vol.Required(CONF_SECONDS): cv.positive_int})

SERVICE_START_PROGRAM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PROGRAM_ID): cv.positive_int}
)

SERVICE_START_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE_ID): cv.positive_int,
        vol.Optional(CONF_ZONE_RUN_TIME, default=DEFAULT_ZONE_RUN): cv.positive_int,
    }
)

SERVICE_STOP_PROGRAM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PROGRAM_ID): cv.positive_int}
)

SERVICE_STOP_ZONE_SCHEMA = vol.Schema({vol.Required(CONF_ZONE_ID): cv.positive_int})

CONFIG_SCHEMA = cv.deprecated(DOMAIN, invalidation_version="0.119")

PLATFORMS = ["binary_sensor", "sensor", "switch"]


async def async_update_programs_and_zones(hass, config_entry):
    """Update program and zone DataUpdateCoordinators.

    Program and zone updates always go together because of how linked they are:
    programs affect zones and certain combinations of zones affect programs.

    Note that this call does not take into account interested entities when making
    the API calls; we make the reasonable assumption that switches will always be
    enabled.
    """
    coordinators = [
        hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id][DATA_PROGRAMS],
        hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id][DATA_ZONES],
    ]

    tasks = [coordinator.async_refresh() for coordinator in coordinators]

    await asyncio.gather(*tasks)


async def async_setup(hass, config):
    """Set up the RainMachine component."""
    hass.data[DOMAIN] = {DATA_CONTROLLER: {}, DATA_COORDINATOR: {}}
    return True


async def async_setup_entry(hass, config_entry):
    """Set up RainMachine as config entry."""
    hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id] = {}

    entry_updates = {}
    if not config_entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = config_entry.data[CONF_IP_ADDRESS]
    if CONF_ZONE_RUN_TIME in config_entry.data:
        # If a zone run time exists in the config entry's data, pop it and move it to
        # options:
        data = {**config_entry.data}
        entry_updates["data"] = data
        entry_updates["options"] = {
            **config_entry.options,
            CONF_ZONE_RUN_TIME: data.pop(CONF_ZONE_RUN_TIME),
        }
    if entry_updates:
        hass.config_entries.async_update_entry(config_entry, **entry_updates)

    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(session=websession)

    try:
        await client.load_local(
            config_entry.data[CONF_IP_ADDRESS],
            config_entry.data[CONF_PASSWORD],
            port=config_entry.data[CONF_PORT],
            ssl=config_entry.data.get(CONF_SSL, DEFAULT_SSL),
        )
    except RainMachineError as err:
        LOGGER.error("An error occurred: %s", err)
        raise ConfigEntryNotReady from err

    # regenmaschine can load multiple controllers at once, but we only grab the one
    # we loaded above:
    controller = hass.data[DOMAIN][DATA_CONTROLLER][config_entry.entry_id] = next(
        iter(client.controllers.values())
    )

    data_init_tasks = []
    for api_category in [
        DATA_PROGRAMS,
        DATA_PROVISION_SETTINGS,
        DATA_RESTRICTIONS_CURRENT,
        DATA_RESTRICTIONS_UNIVERSAL,
        DATA_ZONES,
    ]:
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id][
            api_category
        ] = RainMachineCoordinator(
            hass, controller=controller, api_category=api_category
        )
        data_init_tasks.append(coordinator.async_refresh())

    await asyncio.gather(*data_init_tasks)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    @_verify_domain_control
    async def disable_program(call):
        """Disable a program."""
        await controller.programs.disable(call.data[CONF_PROGRAM_ID])
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def disable_zone(call):
        """Disable a zone."""
        await controller.zones.disable(call.data[CONF_ZONE_ID])
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def enable_program(call):
        """Enable a program."""
        await controller.programs.enable(call.data[CONF_PROGRAM_ID])
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def enable_zone(call):
        """Enable a zone."""
        await controller.zones.enable(call.data[CONF_ZONE_ID])
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def pause_watering(call):
        """Pause watering for a set number of seconds."""
        await controller.watering.pause_all(call.data[CONF_SECONDS])
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def start_program(call):
        """Start a particular program."""
        await controller.programs.start(call.data[CONF_PROGRAM_ID])
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def start_zone(call):
        """Start a particular zone for a certain amount of time."""
        await controller.zones.start(
            call.data[CONF_ZONE_ID], call.data[CONF_ZONE_RUN_TIME]
        )
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def stop_all(call):
        """Stop all watering."""
        await controller.watering.stop_all()
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def stop_program(call):
        """Stop a program."""
        await controller.programs.stop(call.data[CONF_PROGRAM_ID])
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def stop_zone(call):
        """Stop a zone."""
        await controller.zones.stop(call.data[CONF_ZONE_ID])
        await async_update_programs_and_zones()

    @_verify_domain_control
    async def unpause_watering(call):
        """Unpause watering."""
        await controller.watering.unpause_all()
        await async_update_programs_and_zones()

    for service, method, schema in [
        ("disable_program", disable_program, SERVICE_ALTER_PROGRAM),
        ("disable_zone", disable_zone, SERVICE_ALTER_ZONE),
        ("enable_program", enable_program, SERVICE_ALTER_PROGRAM),
        ("enable_zone", enable_zone, SERVICE_ALTER_ZONE),
        ("pause_watering", pause_watering, SERVICE_PAUSE_WATERING),
        ("start_program", start_program, SERVICE_START_PROGRAM_SCHEMA),
        ("start_zone", start_zone, SERVICE_START_ZONE_SCHEMA),
        ("stop_all", stop_all, {}),
        ("stop_program", stop_program, SERVICE_STOP_PROGRAM_SCHEMA),
        ("stop_zone", stop_zone, SERVICE_STOP_ZONE_SCHEMA),
        ("unpause_watering", unpause_watering, {}),
    ]:
        hass.services.async_register(DOMAIN, service, method, schema=schema)

    config_entry.add_update_listener(async_reload_entry)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an OpenUV config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(config_entry.entry_id)

    return unload_ok


async def async_reload_entry(hass, config_entry):
    """Handle an options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class RainMachineEntity(CoordinatorEntity):
    """Define a generic RainMachine entity."""

    def __init__(self, coordinator, controller):
        """Initialize."""
        super().__init__(coordinator)
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._config_entry = None
        self._controller = controller
        self._device_class = None
        self._name = None

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.rainmachine.controller.mac)},
            "name": self.rainmachine.controller.name,
            "manufacturer": "RainMachine",
            "model": (
                f"Version {self.rainmachine.controller.hardware_version} "
                f"(API: {self.rainmachine.controller.api_version})"
            ),
            "sw_version": self.rainmachine.controller.software_version,
        }

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @callback
    def _update_state(self):
        """Update the state."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    @callback
    def update_from_latest_data(self):
        """Update the entity."""
        raise NotImplementedError
