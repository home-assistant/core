"""The Electrolux integration."""

from asyncio import CancelledError
from collections.abc import Awaitable, Callable
import logging

from electrolux_group_developer_sdk.auth.token_manager import TokenManager
from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.failed_connection_exception import (
    FailedConnectionException,
)

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import ElectroluxApiClient
from .const import CONF_REFRESH_TOKEN, DOMAIN, NEW_APPLIANCE, USER_AGENT
from .coordinator import (
    ElectroluxConfigEntry,
    ElectroluxData,
    ElectroluxDataUpdateCoordinator,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ElectroluxConfigEntry) -> bool:
    """Set up Electrolux integration entry."""

    def save_tokens(new_access: str, new_refresh: str, api_key: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_API_KEY: api_key,
                CONF_ACCESS_TOKEN: new_access,
                CONF_REFRESH_TOKEN: new_refresh,
            },
        )

    token_manager = ElectroluxTokenManager(hass, entry, save_tokens)
    appliance_client = ApplianceClient(
        token_manager=token_manager, external_user_agent=USER_AGENT
    )

    # Check during integration initialization if we are able to set it up correctly
    try:
        await appliance_client.test_connection()
    except FailedConnectionException as e:
        raise ConfigEntryAuthFailed("Connection with client failed.") from e

    client = ElectroluxApiClient(appliance_client)
    appliances = await client.fetch_appliance_data()

    coordinators: dict[str, ElectroluxDataUpdateCoordinator] = {}
    on_livestream_opening_callback_list: list[Callable[[], Awaitable[None]]] = []

    async def check_for_new_devices_callback() -> None:
        """Trigger _check_for_new_devices asynchronously."""
        await _check_for_new_devices(hass, entry, client)

    on_livestream_opening_callback_list.append(check_for_new_devices_callback)

    for appliance in appliances:
        appliance_id = appliance.appliance.applianceId
        coordinator = ElectroluxDataUpdateCoordinator(
            hass, entry, client=client, appliance_id=appliance_id
        )

        await coordinator.async_config_entry_first_refresh()

        # Subscribe this coordinator to its appliance events
        client.add_listener(appliance_id, coordinator.callback_handle_event)

        coordinators[appliance_id] = coordinator
        # Device state is refreshed whenever the SSE connection opens.
        on_livestream_opening_callback_list.append(coordinator.async_refresh)

    sse_task = entry.async_create_background_task(
        hass,
        appliance_client.start_event_stream(on_livestream_opening_callback_list),
        "electrolux event listener",
    )

    entry.runtime_data = ElectroluxData(
        client=client,
        appliances=appliances,
        coordinators=coordinators,
        sse_task=sse_task,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElectroluxConfigEntry) -> bool:
    """Unload a config entry."""
    # Remove SSE listeners
    runtime_data = entry.runtime_data
    if runtime_data:
        coordinators = runtime_data.coordinators
        for coordinator in coordinators.values():
            coordinator.remove_listeners()

        # Cancel SSE task
        data = entry.runtime_data
        sse_task = data.sse_task
        if sse_task:
            sse_task.cancel()
            try:
                await sse_task
            except CancelledError:
                _LOGGER.info("SSE stream cancelled for entry %s", entry.entry_id)

    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


class ElectroluxTokenManager(TokenManager):
    """Token Manager for Electrolux integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ElectroluxConfigEntry,
        on_token_update: Callable[[str, str, str], None],
    ) -> None:
        """Initialize Token Manager."""
        self._hass = hass
        self._entry = entry
        api_key = entry.data.get(CONF_API_KEY)
        refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
        access_token = entry.data.get(CONF_ACCESS_TOKEN)
        if access_token and refresh_token and api_key:
            super().__init__(access_token, refresh_token, api_key, on_token_update)


async def _check_for_new_devices(
    hass: HomeAssistant, entry: ElectroluxConfigEntry, client: ElectroluxApiClient
) -> None:
    """Fetch appliances from API and trigger discovery for any new ones."""
    _LOGGER.info("Checking for new devices")
    device_registry = dr.async_get(hass)

    data = entry.runtime_data
    coordinators = data.coordinators
    appliances = await client.fetch_appliance_data()

    existing_ids = set(coordinators.keys())

    for appliance in appliances:
        appliance_id = appliance.appliance.applianceId
        # Detect NEW appliances
        if appliance_id not in existing_ids:
            # Create coordinator for appliance
            coordinator = ElectroluxDataUpdateCoordinator(
                hass, entry, client=client, appliance_id=appliance_id
            )

            await coordinator.async_refresh()

            client.add_listener(appliance_id, coordinator.callback_handle_event)
            data.coordinators[appliance_id] = coordinator

            # Notify all platforms
            async_dispatcher_send(hass, f"{NEW_APPLIANCE}_{entry.entry_id}", appliance)

    # Detect MISSING appliances
    discovered_ids = {appliance.appliance.applianceId for appliance in appliances}
    missing_ids = existing_ids - discovered_ids
    for missing_id in missing_ids:
        _LOGGER.warning("Appliance %s no longer found, removing", missing_id)

        # Remove coordinator
        coordinators.pop(missing_id, None)
        client.remove_all_listeners_by_appliance_id(missing_id)

        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, missing_id)}
        )

        if device_entry:
            device_registry.async_remove_device(device_entry.id)
