"""The CatGenie integration."""

from __future__ import annotations

from contextlib import AsyncExitStack

from catgenie import CatGenieAuth, CatGenieClient, Credentials, Device
from catgenie.exceptions import CatGenieAuthenticationError, CatGenieException

from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .coordinator import (
    CatGenieConfigEntry,
    CatGenieDeviceCoordinator,
    CatGenieRuntimeData,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CatGenieConfigEntry) -> bool:
    """Set up CatGenie from a config entry."""
    credentials = Credentials(refresh_token=entry.data[CONF_TOKEN])
    stack = AsyncExitStack()

    auth = CatGenieAuth()
    await stack.enter_async_context(auth)
    auth.credentials = credentials

    # Obtain a fresh access token using the stored refresh token
    try:
        credentials = await auth.refresh()
    except CatGenieAuthenticationError as err:
        await stack.aclose()
        raise ConfigEntryAuthFailed(
            translation_domain="catgenie",
            translation_key="authentication_failed",
        ) from err
    except CatGenieException as err:
        await stack.aclose()
        raise ConfigEntryNotReady(
            translation_domain="catgenie",
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err

    client = CatGenieClient(credentials)
    await stack.enter_async_context(client)
    client.set_auth(auth)

    # Fetch all devices and create a coordinator for each
    try:
        devices: list[Device] = await client.get_devices()
    except Exception as err:
        await stack.aclose()
        raise ConfigEntryNotReady(
            translation_domain="catgenie",
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err

    device_coordinators: dict[str, CatGenieDeviceCoordinator] = {}
    for device in devices:
        coordinator = CatGenieDeviceCoordinator(hass, entry, client, auth, device)
        await coordinator.async_config_entry_first_refresh()
        device_coordinators[device.manufacturer_id] = coordinator

    entry.runtime_data = CatGenieRuntimeData(
        auth=auth,
        client=client,
        device_coordinators=device_coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CatGenieConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
