"""Platform for the Daikin AC."""

import aiohttp
from daikin_onecta.exceptions import OnectaError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, OAuth2TokenRequestError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.helpers.device_registry import AnyDeviceEntry, DeviceEntry

from .const import DOMAIN
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .daikin_api import DaikinApi, gateway_site_membership

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.WATER_HEATER,
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DaikinOnectaConfigEntry
) -> bool:
    """Establish connection with Daikin."""
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, config_entry
            )
        )
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    daikin_api = DaikinApi(hass, config_entry, implementation)

    try:
        await daikin_api.async_get_access_token()
    except OAuth2TokenRequestError:
        raise
    except (TimeoutError, aiohttp.ClientError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_token_request_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    config_entry.runtime_data = OnectaDataUpdateCoordinator(
        hass, config_entry, daikin_api
    )

    await config_entry.runtime_data.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DaikinOnectaConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    device_entry: AnyDeviceEntry,
) -> bool:
    """Allow explicit removal only for gateways confirmed absent from the account."""
    if config_entry.state is not ConfigEntryState.LOADED or not isinstance(
        device_entry, DeviceEntry
    ):
        return False
    gateway_id = next(
        (
            identifier
            for domain, identifier in device_entry.identifiers
            if domain == DOMAIN
        ),
        None,
    )
    account_id = config_entry.unique_id or config_entry.entry_id
    if gateway_id is None or gateway_id == f"account_{account_id}":
        return False

    coordinator = config_entry.runtime_data
    if not coordinator.last_update_success or (
        (device := (coordinator.data or {}).get(gateway_id)) is not None
        and device.present_in_cloud
    ):
        return False
    try:
        sites = await coordinator.api.get_sites()
    except OnectaError, aiohttp.ClientError, TimeoutError:
        return False

    # Polling may have restored the gateway while the on-demand lookup awaited.
    if gateway_site_membership(sites, gateway_id) is not False or (
        not coordinator.last_update_success
        or (
            (device := (coordinator.data or {}).get(gateway_id)) is not None
            and device.present_in_cloud
        )
    ):
        return False
    if coordinator.data is not None:
        coordinator.data.pop(gateway_id, None)
    return True
