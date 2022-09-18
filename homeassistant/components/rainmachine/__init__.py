"""Support for RainMachine devices."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import Any

from regenmaschine import Client
from regenmaschine.controller import Controller
from regenmaschine.errors import RainMachineError, UnknownAPICallError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed
from homeassistant.util.dt import as_timestamp, utcnow
from homeassistant.util.network import is_ip_address

from .config_flow import get_client_controller
from .const import (
    CONF_ZONE_RUN_TIME,
    DATA_API_VERSIONS,
    DATA_MACHINE_FIRMWARE_UPDATE_STATUS,
    DATA_PROGRAMS,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_CURRENT,
    DATA_RESTRICTIONS_UNIVERSAL,
    DATA_ZONES,
    DOMAIN,
    LOGGER,
)
from .model import RainMachineEntityDescription
from .util import RainMachineDataUpdateCoordinator

DEFAULT_SSL = True

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

CONF_CONDITION = "condition"
CONF_DEWPOINT = "dewpoint"
CONF_DURATION = "duration"
CONF_ET = "et"
CONF_MAXRH = "maxrh"
CONF_MAXTEMP = "maxtemp"
CONF_MINRH = "minrh"
CONF_MINTEMP = "mintemp"
CONF_PRESSURE = "pressure"
CONF_QPF = "qpf"
CONF_RAIN = "rain"
CONF_SECONDS = "seconds"
CONF_SOLARRAD = "solarrad"
CONF_TEMPERATURE = "temperature"
CONF_TIMESTAMP = "timestamp"
CONF_WEATHER = "weather"
CONF_WIND = "wind"

# Config Validators for Weather Service Data
CV_WX_DATA_VALID_PERCENTAGE = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))
CV_WX_DATA_VALID_TEMP_RANGE = vol.All(vol.Coerce(float), vol.Range(min=-40.0, max=40.0))
CV_WX_DATA_VALID_RAIN_RANGE = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1000.0))
CV_WX_DATA_VALID_WIND_SPEED = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=65.0))
CV_WX_DATA_VALID_PRESSURE = vol.All(vol.Coerce(float), vol.Range(min=60.0, max=110.0))
CV_WX_DATA_VALID_SOLARRAD = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0))

SERVICE_NAME_PAUSE_WATERING = "pause_watering"
SERVICE_NAME_PUSH_WEATHER_DATA = "push_weather_data"
SERVICE_NAME_RESTRICT_WATERING = "restrict_watering"
SERVICE_NAME_STOP_ALL = "stop_all"
SERVICE_NAME_UNPAUSE_WATERING = "unpause_watering"
SERVICE_NAME_UNRESTRICT_WATERING = "unrestrict_watering"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
    }
)

SERVICE_PAUSE_WATERING_SCHEMA = SERVICE_SCHEMA.extend(
    {
        vol.Required(CONF_SECONDS): cv.positive_int,
    }
)

SERVICE_PUSH_WEATHER_DATA_SCHEMA = SERVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_TIMESTAMP): cv.positive_float,
        vol.Optional(CONF_MINTEMP): CV_WX_DATA_VALID_TEMP_RANGE,
        vol.Optional(CONF_MAXTEMP): CV_WX_DATA_VALID_TEMP_RANGE,
        vol.Optional(CONF_TEMPERATURE): CV_WX_DATA_VALID_TEMP_RANGE,
        vol.Optional(CONF_WIND): CV_WX_DATA_VALID_WIND_SPEED,
        vol.Optional(CONF_SOLARRAD): CV_WX_DATA_VALID_SOLARRAD,
        vol.Optional(CONF_QPF): CV_WX_DATA_VALID_RAIN_RANGE,
        vol.Optional(CONF_RAIN): CV_WX_DATA_VALID_RAIN_RANGE,
        vol.Optional(CONF_ET): CV_WX_DATA_VALID_RAIN_RANGE,
        vol.Optional(CONF_MINRH): CV_WX_DATA_VALID_PERCENTAGE,
        vol.Optional(CONF_MAXRH): CV_WX_DATA_VALID_PERCENTAGE,
        vol.Optional(CONF_CONDITION): cv.string,
        vol.Optional(CONF_PRESSURE): CV_WX_DATA_VALID_PRESSURE,
        vol.Optional(CONF_DEWPOINT): CV_WX_DATA_VALID_TEMP_RANGE,
    }
)

SERVICE_RESTRICT_WATERING_SCHEMA = SERVICE_SCHEMA.extend(
    {
        vol.Required(CONF_DURATION): cv.time_period,
    }
)

COORDINATOR_UPDATE_INTERVAL_MAP = {
    DATA_API_VERSIONS: timedelta(minutes=1),
    DATA_MACHINE_FIRMWARE_UPDATE_STATUS: timedelta(seconds=15),
    DATA_PROGRAMS: timedelta(seconds=30),
    DATA_PROVISION_SETTINGS: timedelta(minutes=1),
    DATA_RESTRICTIONS_CURRENT: timedelta(minutes=1),
    DATA_RESTRICTIONS_UNIVERSAL: timedelta(minutes=1),
    DATA_ZONES: timedelta(seconds=15),
}


@dataclass
class RainMachineData:
    """Define an object to be stored in `hass.data`."""

    controller: Controller
    coordinators: dict[str, RainMachineDataUpdateCoordinator]


@callback
def async_get_controller_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> Controller:
    """Get the controller related to a service call (by device ID)."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)

    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ValueError(f"Invalid RainMachine device ID: {device_id}")

    for entry_id in device_entry.config_entries:
        if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN:
            data: RainMachineData = hass.data[DOMAIN][entry_id]
            return data.controller

    raise ValueError(f"No controller for device ID: {device_id}")


async def async_update_programs_and_zones(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Update program and zone DataUpdateCoordinators.

    Program and zone updates always go together because of how linked they are:
    programs affect zones and certain combinations of zones affect programs.
    """
    data: RainMachineData = hass.data[DOMAIN][entry.entry_id]

    await asyncio.gather(
        *[
            data.coordinators[DATA_PROGRAMS].async_refresh(),
            data.coordinators[DATA_ZONES].async_refresh(),
        ]
    )


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up RainMachine as config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(session=websession)

    try:
        await client.load_local(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_PASSWORD],
            port=entry.data[CONF_PORT],
            use_ssl=entry.data.get(CONF_SSL, DEFAULT_SSL),
        )
    except RainMachineError as err:
        raise ConfigEntryNotReady from err

    # regenmaschine can load multiple controllers at once, but we only grab the one
    # we loaded above:
    controller = get_client_controller(client)

    entry_updates: dict[str, Any] = {}
    if not entry.unique_id or is_ip_address(entry.unique_id):
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = controller.mac
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

    async def async_update(api_category: str) -> dict:
        """Update the appropriate API data based on a category."""
        data: dict = {}

        try:
            if api_category == DATA_API_VERSIONS:
                data = await controller.api.versions()
            elif api_category == DATA_MACHINE_FIRMWARE_UPDATE_STATUS:
                data = await controller.machine.get_firmware_update_status()
            elif api_category == DATA_PROGRAMS:
                data = await controller.programs.all(include_inactive=True)
            elif api_category == DATA_PROVISION_SETTINGS:
                data = await controller.provisioning.settings()
            elif api_category == DATA_RESTRICTIONS_CURRENT:
                data = await controller.restrictions.current()
            elif api_category == DATA_RESTRICTIONS_UNIVERSAL:
                data = await controller.restrictions.universal()
            else:
                data = await controller.zones.all(details=True, include_inactive=True)
        except UnknownAPICallError:
            LOGGER.info(
                "Skipping unsupported API call for controller %s: %s",
                controller.name,
                api_category,
            )
        except RainMachineError as err:
            raise UpdateFailed(err) from err

        return data

    async def async_init_coordinator(
        coordinator: RainMachineDataUpdateCoordinator,
    ) -> None:
        """Initialize a RainMachineDataUpdateCoordinator."""
        await coordinator.async_initialize()
        await coordinator.async_config_entry_first_refresh()

    controller_init_tasks = []
    coordinators = {}
    for api_category, update_interval in COORDINATOR_UPDATE_INTERVAL_MAP.items():
        coordinator = coordinators[api_category] = RainMachineDataUpdateCoordinator(
            hass,
            entry=entry,
            name=f'{controller.name} ("{api_category}")',
            api_category=api_category,
            update_interval=update_interval,
            update_method=partial(async_update, api_category),
        )
        controller_init_tasks.append(async_init_coordinator(coordinator))

    await asyncio.gather(*controller_init_tasks)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = RainMachineData(
        controller=controller, coordinators=coordinators
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    async def async_pause_watering(call: ServiceCall) -> None:
        """Pause watering for a set number of seconds."""
        controller = async_get_controller_for_service_call(hass, call)
        await controller.watering.pause_all(call.data[CONF_SECONDS])
        await async_update_programs_and_zones(hass, entry)

    async def async_push_weather_data(call: ServiceCall) -> None:
        """Push weather data to the device."""
        controller = async_get_controller_for_service_call(hass, call)
        await controller.parsers.post_data(
            {
                CONF_WEATHER: [
                    {
                        key: value
                        for key, value in call.data.items()
                        if key != CONF_DEVICE_ID
                    }
                ]
            }
        )

    async def async_restrict_watering(call: ServiceCall) -> None:
        """Restrict watering for a time period."""
        controller = async_get_controller_for_service_call(hass, call)
        duration = call.data[CONF_DURATION]
        await controller.restrictions.set_universal(
            {
                "rainDelayStartTime": round(as_timestamp(utcnow())),
                "rainDelayDuration": duration.total_seconds(),
            },
        )
        await async_update_programs_and_zones(hass, entry)

    async def async_stop_all(call: ServiceCall) -> None:
        """Stop all watering."""
        controller = async_get_controller_for_service_call(hass, call)
        await controller.watering.stop_all()
        await async_update_programs_and_zones(hass, entry)

    async def async_unpause_watering(call: ServiceCall) -> None:
        """Unpause watering."""
        controller = async_get_controller_for_service_call(hass, call)
        await controller.watering.unpause_all()
        await async_update_programs_and_zones(hass, entry)

    async def async_unrestrict_watering(call: ServiceCall) -> None:
        """Unrestrict watering."""
        controller = async_get_controller_for_service_call(hass, call)
        await controller.restrictions.set_universal(
            {
                "rainDelayStartTime": round(as_timestamp(utcnow())),
                "rainDelayDuration": 0,
            },
        )
        await async_update_programs_and_zones(hass, entry)

    for service_name, schema, method in (
        (
            SERVICE_NAME_PAUSE_WATERING,
            SERVICE_PAUSE_WATERING_SCHEMA,
            async_pause_watering,
        ),
        (
            SERVICE_NAME_PUSH_WEATHER_DATA,
            SERVICE_PUSH_WEATHER_DATA_SCHEMA,
            async_push_weather_data,
        ),
        (
            SERVICE_NAME_RESTRICT_WATERING,
            SERVICE_RESTRICT_WATERING_SCHEMA,
            async_restrict_watering,
        ),
        (SERVICE_NAME_STOP_ALL, SERVICE_SCHEMA, async_stop_all),
        (SERVICE_NAME_UNPAUSE_WATERING, SERVICE_SCHEMA, async_unpause_watering),
        (
            SERVICE_NAME_UNRESTRICT_WATERING,
            SERVICE_SCHEMA,
            async_unrestrict_watering,
        ),
    ):
        if hass.services.has_service(DOMAIN, service_name):
            continue
        hass.services.async_register(DOMAIN, service_name, method, schema=schema)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an RainMachine config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        # If this is the last loaded instance of RainMachine, deregister any services
        # defined during integration setup:
        for service_name in (
            SERVICE_NAME_PAUSE_WATERING,
            SERVICE_NAME_PUSH_WEATHER_DATA,
            SERVICE_NAME_RESTRICT_WATERING,
            SERVICE_NAME_STOP_ALL,
            SERVICE_NAME_UNPAUSE_WATERING,
            SERVICE_NAME_UNRESTRICT_WATERING,
        ):
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    version = entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Update unique IDs to be consistent across platform (including removing
    # the silly removal of colons in the MAC address that was added originally):
    if version == 1:
        version = entry.version = 2

        @callback
        def migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, Any]:
            """Migrate the unique ID to a new format."""
            unique_id_pieces = entity_entry.unique_id.split("_")
            old_mac = unique_id_pieces[0]
            new_mac = ":".join(old_mac[i : i + 2] for i in range(0, len(old_mac), 2))
            unique_id_pieces[0] = new_mac

            if entity_entry.entity_id.startswith("switch"):
                unique_id_pieces[1] = unique_id_pieces[1][11:].lower()

            return {"new_unique_id": "_".join(unique_id_pieces)}

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)

    LOGGER.info("Migration to version %s successful", version)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class RainMachineEntity(CoordinatorEntity):
    """Define a generic RainMachine entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        data: RainMachineData,
        description: RainMachineEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(data.coordinators[description.api_category])

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{data.controller.mac}_{description.key}"
        self._entry = entry
        self._data = data
        self._version_coordinator = data.coordinators[DATA_API_VERSIONS]
        self.entity_description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this controller."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._data.controller.mac)},
            configuration_url=(
                f"https://{self._entry.data[CONF_IP_ADDRESS]}:"
                f"{self._entry.data[CONF_PORT]}"
            ),
            connections={(dr.CONNECTION_NETWORK_MAC, self._data.controller.mac)},
            name=str(self._data.controller.name).capitalize(),
            manufacturer="RainMachine",
            model=(
                f"Version {self._version_coordinator.data['hwVer']} "
                f"(API: {self._version_coordinator.data['apiVer']})"
            ),
            sw_version=self._version_coordinator.data["swVer"],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._version_coordinator.async_add_listener(
                self._handle_coordinator_update, self.coordinator_context
            )
        )
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
