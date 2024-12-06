"""The Wolf SmartSet Service integration."""

from datetime import timedelta
import logging
import voluptuous as vol

from httpx import RequestError
from wolf_comm import VALUE_ID, STATE
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import FetchFailed, ParameterReadError, WolfClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COORDINATOR,
    DEVICE_GATEWAY,
    DEVICE_ID,
    DEVICE_NAME,
    DOMAIN,
    PARAMETERS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wolf SmartSet Service from a config entry."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    device_name = entry.data[DEVICE_NAME]
    device_id = entry.data[DEVICE_ID]
    gateway_id = entry.data[DEVICE_GATEWAY]
    refetch_parameters = False
    _LOGGER.debug(
        "Setting up wolflink integration for device: %s (ID: %s, gateway: %s)",
        device_name,
        device_id,
        gateway_id,
    )

    wolf_client = WolfClient(
        username,
        password,
        client=get_async_client(hass=hass, verify_ssl=False),
    )

    parameters = await fetch_parameters_init(wolf_client, gateway_id, device_id)

    async def async_update_data():
        """Update all stored entities for Wolf SmartSet."""
        try:
            nonlocal refetch_parameters
            nonlocal parameters
            if not await wolf_client.fetch_system_state_list(device_id, gateway_id):
                refetch_parameters = True
                raise UpdateFailed(
                    "Could not fetch values from server because device is Offline."
                )
            if refetch_parameters:
                parameters = await fetch_parameters(wolf_client, gateway_id, device_id)
                hass.data[DOMAIN][entry.entry_id][PARAMETERS] = parameters
                refetch_parameters = False
            values = {
                v.value_id: v.value
                for v in await wolf_client.fetch_value(
                    gateway_id, device_id, parameters
                )
            }
            return {
                parameter.parameter_id: (
                    parameter.value_id,
                    values[parameter.value_id],
                )
                for parameter in parameters
                if parameter.value_id in values
            }
        except RequestError as exception:
            raise UpdateFailed(
                f"Error communicating with API: {exception}"
            ) from exception
        except FetchFailed as exception:
            raise UpdateFailed(
                f"Could not fetch values from server due to: {exception}"
            ) from exception
        except ParameterReadError as exception:
            refetch_parameters = True
            raise UpdateFailed(
                "Could not fetch values for parameter. Refreshing value IDs."
            ) from exception
        except InvalidAuth as exception:
            raise UpdateFailed("Invalid authentication during update.") from exception

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=60),
    )

    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id][PARAMETERS] = parameters
    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator
    hass.data[DOMAIN][entry.entry_id][DEVICE_ID] = device_id

    async def async_set_value(call):
        """Handle the service call to write a value to the Wolf SmartSet system."""
        value_id = call.data["value_id"]  # the id of the specific parameter to change
        state = call.data["state"]  # the new value to set
        gateway_id_ = call.data["gateway_id"]
        system_id = call.data["system_id"]

        try:
            value_id = str(value_id)
            state = str(state)
            value_data = {VALUE_ID: value_id, STATE: state}
            await wolf_client.write_value(gateway_id_, system_id, value_data)
            _LOGGER.info(
                "Successfully wrote value %s to device %s", value_data, system_id
            )
        except RequestError as e:
            _LOGGER.error("Network error when writing value: %s", e)
            raise
        except InvalidAuth as e:
            _LOGGER.error("Authentication failed while writing value: %s", e)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error occurred when writing value: %s", e)
            raise

    # register the service # changes here require changes in services.yaml
    hass.services.async_register(
        domain=DOMAIN,
        service="set_value",
        service_func=async_set_value,
        schema=vol.Schema(
            {
                vol.Required("value_id"): vol.Any(str, int),
                vol.Required("state"): vol.Any(str, int, float),
                vol.Optional("gateway_id", default=gateway_id): vol.Coerce(int),
                vol.Optional("system_id", default=device_id): vol.Coerce(int),
            }
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # convert unique_id to string
    if entry.version == 1 and entry.minor_version == 1:
        if isinstance(entry.unique_id, int):
            hass.config_entries.async_update_entry(
                entry, unique_id=str(entry.unique_id)
            )
            device_registry = dr.async_get(hass)
            for device in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            ):
                new_identifiers = set()
                for identifier in device.identifiers:
                    if identifier[0] == DOMAIN:
                        new_identifiers.add((DOMAIN, str(identifier[1])))
                    else:
                        new_identifiers.add(identifier)
                device_registry.async_update_device(
                    device.id, new_identifiers=new_identifiers
                )
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def fetch_parameters(client: WolfClient, gateway_id: int, device_id: int):
    """Fetch all available parameters with usage of WolfClient.

    By default Reglertyp entity is removed because API will not provide value for this parameter.
    """
    fetched_parameters = await client.fetch_parameters(gateway_id, device_id)
    return [param for param in fetched_parameters if param.name != "Reglertyp"]


async def fetch_parameters_init(client: WolfClient, gateway_id: int, device_id: int):
    """Fetch all available parameters with usage of WolfClient but handles all exceptions and results in ConfigEntryNotReady."""
    try:
        return await fetch_parameters(client, gateway_id, device_id)
    except (FetchFailed, RequestError) as exception:
        raise ConfigEntryNotReady(
            f"Error communicating with API: {exception}"
        ) from exception
