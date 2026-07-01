"""Support for RainMachine devices."""

from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import Any

from regenmaschine import Client
from regenmaschine.controller import Controller
from regenmaschine.errors import RainMachineError, UnknownAPICallError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.network import is_ip_address

from .config_flow import get_client_controller
from .const import (
    CONF_ALLOW_INACTIVE_ZONES_TO_RUN,
    CONF_DEFAULT_ZONE_RUN_TIME,
    CONF_USE_APP_RUN_TIMES,
    DATA_API_VERSIONS,
    DATA_MACHINE_FIRMWARE_UPDATE_STATUS,
    DATA_PROGRAMS,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_CURRENT,
    DATA_RESTRICTIONS_UNIVERSAL,
    DATA_ZONES,
    DEFAULT_ZONE_RUN,
    DOMAIN,
    LOGGER,
)
from .coordinator import RainMachineDataUpdateCoordinator
from .services import async_setup_services

API_URL_REFERENCE = (
    "https://rainmachine.docs.apiary.io/#reference/weather-services/parserdata/post"
)

DEFAULT_SSL = True

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

COORDINATOR_UPDATE_INTERVAL_MAP = {
    DATA_API_VERSIONS: timedelta(minutes=1),
    DATA_MACHINE_FIRMWARE_UPDATE_STATUS: timedelta(seconds=15),
    DATA_PROGRAMS: timedelta(seconds=30),
    DATA_PROVISION_SETTINGS: timedelta(minutes=1),
    DATA_RESTRICTIONS_CURRENT: timedelta(minutes=1),
    DATA_RESTRICTIONS_UNIVERSAL: timedelta(minutes=1),
    DATA_ZONES: timedelta(seconds=15),
}


type RainMachineConfigEntry = ConfigEntry[RainMachineData]


@dataclass
class RainMachineData:
    """Define an object to be stored in `entry.runtime_data`."""

    controller: Controller
    coordinators: dict[str, RainMachineDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Rainmachine."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RainMachineConfigEntry) -> bool:
    """Set up RainMachine as config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(session=websession)
    ip_address = entry.data[CONF_IP_ADDRESS]

    try:
        await client.load_local(
            ip_address,
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

    if CONF_DEFAULT_ZONE_RUN_TIME in entry.data:
        # If a zone run time exists in the config entry's data, pop it and move it to
        # options:
        data = {**entry.data}
        entry_updates["data"] = data
        entry_updates["options"] = {
            **entry.options,
            CONF_DEFAULT_ZONE_RUN_TIME: data.pop(CONF_DEFAULT_ZONE_RUN_TIME),
        }
    entry_updates["options"] = {**entry.options}
    if CONF_USE_APP_RUN_TIMES not in entry.options:
        entry_updates["options"][CONF_USE_APP_RUN_TIMES] = False
    if CONF_DEFAULT_ZONE_RUN_TIME not in entry.options:
        entry_updates["options"][CONF_DEFAULT_ZONE_RUN_TIME] = DEFAULT_ZONE_RUN
    if CONF_ALLOW_INACTIVE_ZONES_TO_RUN not in entry.options:
        entry_updates["options"][CONF_ALLOW_INACTIVE_ZONES_TO_RUN] = False
    if entry_updates:
        hass.config_entries.async_update_entry(entry, **entry_updates)

    if entry.unique_id and controller.mac != entry.unique_id:
        # If the mac address of the device does not match the unique_id
        # of the config entry, it likely means the DHCP lease has expired
        # and the device has been assigned a new IP address. We need to
        # wait for the next discovery to find the device at its new address
        # and update the config entry so we do not mix up devices.
        raise ConfigEntryNotReady(
            f"Unexpected device found at {ip_address}; expected {entry.unique_id}, "
            f"found {controller.mac}"
        )

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
            LOGGER.warning(
                "Skipping unsupported API call for controller %s: %s",
                controller.name,
                api_category,
            )
        except RainMachineError as err:
            raise UpdateFailed(err) from err

        return data

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
        coordinator.async_initialize()
        # Its generally faster not to gather here so we can
        # reuse the connection instead of creating a new
        # connection for each coordinator.
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = RainMachineData(
        controller=controller, coordinators=coordinators
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RainMachineConfigEntry
) -> bool:
    """Unload an RainMachine config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: RainMachineConfigEntry
) -> bool:
    """Migrate an old config entry."""
    version = entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Update unique IDs to be consistent across platform (including removing
    # the silly removal of colons in the MAC address that was added originally):
    if version == 1:
        version = 2
        hass.config_entries.async_update_entry(entry, version=version)

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

    LOGGER.debug("Migration to version %s successful", version)

    return True


async def async_reload_entry(
    hass: HomeAssistant, entry: RainMachineConfigEntry
) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)
