"""Support for RainMachine devices."""
import asyncio
from datetime import timedelta
from functools import partial

from regenmaschine import Client
from regenmaschine.controller import Controller
from regenmaschine.errors import RainMachineError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.service import verify_domain_control
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

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

CONF_PROGRAM_ID = "program_id"
CONF_SECONDS = "seconds"
CONF_ZONE_ID = "zone_id"

DATA_LISTENER = "listener"

DEFAULT_ATTRIBUTION = "Data provided by Green Electronics LLC"
DEFAULT_ICON = "mdi:water"
DEFAULT_SSL = True
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=15)

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

CONFIG_SCHEMA = cv.deprecated(DOMAIN)

PLATFORMS = ["binary_sensor", "sensor", "switch"]


async def async_update_programs_and_zones(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Update program and zone DataUpdateCoordinators.

    Program and zone updates always go together because of how linked they are:
    programs affect zones and certain combinations of zones affect programs.
    """
    await asyncio.gather(
        *[
            hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
                DATA_PROGRAMS
            ].async_refresh(),
            hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
                DATA_ZONES
            ].async_refresh(),
        ]
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the RainMachine component."""
    hass.data[DOMAIN] = {DATA_CONTROLLER: {}, DATA_COORDINATOR: {}, DATA_LISTENER: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RainMachine as config entry."""
    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id] = {}

    entry_updates = {}
    if not entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = entry.data[CONF_IP_ADDRESS]
    if CONF_ZONE_RUN_TIME in entry.data:
        # If a zone run time exists in the config entry's data, pop it and move it to
        # options:
        data = {**entry.data}
        entry_updates["data"] = data
        entry_updates["options"] = {
            **entry.options,
            CONF_ZONE_RUN_TIME: data.pop(CONF_ZONE_RUN_TIME),
        }
    if entry_updates:
        hass.config_entries.async_update_entry(entry, **entry_updates)

    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(session=websession)

    try:
        await client.load_local(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_PASSWORD],
            port=entry.data[CONF_PORT],
            ssl=entry.data.get(CONF_SSL, DEFAULT_SSL),
        )
    except RainMachineError as err:
        LOGGER.error("An error occurred: %s", err)
        raise ConfigEntryNotReady from err

    # regenmaschine can load multiple controllers at once, but we only grab the one
    # we loaded above:
    controller = hass.data[DOMAIN][DATA_CONTROLLER][entry.entry_id] = next(
        iter(client.controllers.values())
    )

    async def async_update(api_category: str) -> dict:
        """Update the appropriate API data based on a category."""
        try:
            if api_category == DATA_PROGRAMS:
                return await controller.programs.all(include_inactive=True)

            if api_category == DATA_PROVISION_SETTINGS:
                return await controller.provisioning.settings()

            if api_category == DATA_RESTRICTIONS_CURRENT:
                return await controller.restrictions.current()

            if api_category == DATA_RESTRICTIONS_UNIVERSAL:
                return await controller.restrictions.universal()

            return await controller.zones.all(details=True, include_inactive=True)
        except RainMachineError as err:
            raise UpdateFailed(err) from err

    controller_init_tasks = []
    for api_category in [
        DATA_PROGRAMS,
        DATA_PROVISION_SETTINGS,
        DATA_RESTRICTIONS_CURRENT,
        DATA_RESTRICTIONS_UNIVERSAL,
        DATA_ZONES,
    ]:
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
            api_category
        ] = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f'{controller.name} ("{api_category}")',
            update_interval=DEFAULT_UPDATE_INTERVAL,
            update_method=partial(async_update, api_category),
        )
        controller_init_tasks.append(coordinator.async_refresh())

    await asyncio.gather(*controller_init_tasks)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    @_verify_domain_control
    async def disable_program(call: ServiceCall):
        """Disable a program."""
        await controller.programs.disable(call.data[CONF_PROGRAM_ID])
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def disable_zone(call: ServiceCall):
        """Disable a zone."""
        await controller.zones.disable(call.data[CONF_ZONE_ID])
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def enable_program(call: ServiceCall):
        """Enable a program."""
        await controller.programs.enable(call.data[CONF_PROGRAM_ID])
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def enable_zone(call: ServiceCall):
        """Enable a zone."""
        await controller.zones.enable(call.data[CONF_ZONE_ID])
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def pause_watering(call: ServiceCall):
        """Pause watering for a set number of seconds."""
        await controller.watering.pause_all(call.data[CONF_SECONDS])
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def start_program(call: ServiceCall):
        """Start a particular program."""
        await controller.programs.start(call.data[CONF_PROGRAM_ID])
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def start_zone(call: ServiceCall):
        """Start a particular zone for a certain amount of time."""
        await controller.zones.start(
            call.data[CONF_ZONE_ID], call.data[CONF_ZONE_RUN_TIME]
        )
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def stop_all(call: ServiceCall):
        """Stop all watering."""
        await controller.watering.stop_all()
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def stop_program(call: ServiceCall):
        """Stop a program."""
        await controller.programs.stop(call.data[CONF_PROGRAM_ID])
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def stop_zone(call: ServiceCall):
        """Stop a zone."""
        await controller.zones.stop(call.data[CONF_ZONE_ID])
        await async_update_programs_and_zones(hass, entry)

    @_verify_domain_control
    async def unpause_watering(call: ServiceCall):
        """Unpause watering."""
        await controller.watering.unpause_all()
        await async_update_programs_and_zones(hass, entry)

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

    hass.data[DOMAIN][DATA_LISTENER][entry.entry_id] = entry.add_update_listener(
        async_reload_entry
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an RainMachine config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)
        cancel_listener = hass.data[DOMAIN][DATA_LISTENER].pop(entry.entry_id)
        cancel_listener()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class RainMachineEntity(CoordinatorEntity):
    """Define a generic RainMachine entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, controller: Controller
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._controller = controller
        self._device_class = None
        # The colons are removed from the device MAC simply because that value
        # (unnecessarily) makes up the existing unique ID formula and we want to avoid
        # a breaking change:
        self._unique_id = controller.mac.replace(":", "")
        self._name = None

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return self._device_class

    @property
    def device_info(self) -> dict:
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._controller.mac)},
            "name": self._controller.name,
            "manufacturer": "RainMachine",
            "model": (
                f"Version {self._controller.hardware_version} "
                f"(API: {self._controller.api_version})"
            ),
            "sw_version": self._controller.software_version,
        }

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @callback
    def _handle_coordinator_update(self):
        """Respond to a DataUpdateCoordinator update."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        raise NotImplementedError
