# Shark IQ Integration.

import asyncio
from contextlib import suppress

import aiohttp
from .sharkiq_pypi.sharkiq import (
    AylaApi,
    SharkIqAuthError,
    SharkIqAuthExpiringError,
    SharkIqAuthVerificationRequiredError,
    SharkIqNotAuthedError,
    get_ayla_api,
)

from homeassistant import exceptions
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    API_BACKEND_AYLA,
    API_BACKEND_SKEGOX,
    API_TIMEOUT,
    CONF_API_BACKEND,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SHARKIQ_REGION_DEFAULT,
    SHARKIQ_REGION_EUROPE,
)
from .coordinator import SharkDevice, SharkIqConfigEntry, SharkIqUpdateCoordinator, SkegoxUpdateCoordinator
from .services import async_setup_services
from .skegox_api import SkegoxApi, SkegoxApiError
from .skegox_auth import (
    SkegoxAuthError,
    SkegoxAuthManager,
    SkegoxAuthRequiresVerificationError,
)
from .skegox_device import SkegoxDevice

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

# Connect to vacuum via Ayla API.
# Returns True on successful sign-in, False on auth errors.
# Raises CannotConnect on timeout. Only handles Ayla (not Skegox) auth.
async def async_connect_or_timeout(ayla_api: AylaApi) -> bool:
    try:
        async with asyncio.timeout(API_TIMEOUT):
            LOGGER.debug("Initialize connection to Ayla networks API")
            await ayla_api.async_sign_in()
    except SharkIqAuthVerificationRequiredError:
        LOGGER.error(
            "SharkNinja is blocking automated login (anti-bot protection). "
            "This is not a credential issue. Wait 24-48 hours without retrying, "
            "then try again. You can still use the SharkClean app in the meantime."
        )
        return False
    except SharkIqAuthError:
        LOGGER.error("Authentication error connecting to Shark IQ api")
        return False
    except TimeoutError as exc:
        LOGGER.error("Timeout expired")
        raise CannotConnect from exc

    return True

# Set up the component.
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True

# Attempt Skegox API setup. Returns (coordinator, devices) or (None, []).
async def _try_skegox_setup(hass: HomeAssistant, config_entry: SharkIqConfigEntry, region: str,) -> tuple[SkegoxUpdateCoordinator | None, list[SkegoxDevice]]:
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    auth_manager = SkegoxAuthManager(hass, config_entry, username, password, region)

    try:
        await auth_manager.ensure_authenticated()
    except SkegoxAuthRequiresVerificationError as exc:
        LOGGER.debug("Skegox auth requires verification: %s", exc)
        await auth_manager.close()
        return None, []
    except SkegoxAuthError as exc:
        LOGGER.debug("Skegox auth failed: %s", exc)
        await auth_manager.close()
        return None, []

    skegox_api = SkegoxApi(auth_manager)

    try:
        await skegox_api.discover()
        raw_devices = await skegox_api.get_all_devices()
    except (SkegoxApiError, SkegoxAuthError) as exc:
        LOGGER.debug("Skegox API error during setup: %s", exc)
        await skegox_api.close()
        return None, []

    if not raw_devices:
        LOGGER.debug("Skegox returned no devices")
        await skegox_api.close()
        return None, []

    devices = []
    for raw in raw_devices:
        device = SkegoxDevice(skegox_api, raw)
        devices.append(device)

    # Fetch zones (MARD protobuf with room/no-go polygon data) and
    # floorRPfile1 (floor plan image protobuf) for each device
    for device in devices:
        mard_body = await skegox_api.fetch_property_file(device.serial_number, "zones")
        if mard_body:
            device.load_mard(mard_body)

        # Fetch floor plan image protobuf
        floor_data = await skegox_api.fetch_property_file(device.serial_number, "floorRPfile1")
        if floor_data:
            device.parse_floor_plan(floor_data)

    device_names = ", ".join(d.name for d in devices)
    LOGGER.info("Found %d Shark device(s) via Skegox API: %s", len(devices), device_names)

    coordinator = SkegoxUpdateCoordinator(hass, config_entry, skegox_api, auth_manager, devices)

    return coordinator, devices

# Attempt Ayla API setup. Returns (coordinator, devices) or (None, []).
async def _try_ayla_setup(hass: HomeAssistant, config_entry: SharkIqConfigEntry, region: str,) -> tuple[SharkIqUpdateCoordinator | None, list[SharkDevice]]:
    new_websession = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar(unsafe=True, quote_cookie=False),)

    ayla_api = get_ayla_api(
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        websession=new_websession,
        europe=(region == SHARKIQ_REGION_EUROPE),
    )

    try:
        if not await async_connect_or_timeout(ayla_api):
            return None, []
    except CannotConnect:
        return None, []

    shark_vacs = await ayla_api.async_get_devices(False)
    if not shark_vacs:
        LOGGER.debug("Ayla returned no devices")
        return None, []

    device_names = ", ".join(d.name for d in shark_vacs)
    LOGGER.info("Found %d Shark device(s) via Ayla API: %s", len(shark_vacs), device_names)

    coordinator = SharkIqUpdateCoordinator(hass, config_entry, ayla_api, shark_vacs)
    return coordinator, shark_vacs

# Initialize the sharkiq platform via config entry.
async def async_setup_entry(hass: HomeAssistant, config_entry: SharkIqConfigEntry) -> bool:
    if CONF_REGION not in config_entry.data:
        hass.config_entries.async_update_entry(config_entry, data={**config_entry.data, CONF_REGION: SHARKIQ_REGION_DEFAULT},)

    region = config_entry.data.get(CONF_REGION, SHARKIQ_REGION_DEFAULT)

    # Try previously stored backend first with fallback to the other.
    # Default to Skegox then Ayla.
    stored_backend = config_entry.data.get(CONF_API_BACKEND)

    if stored_backend == API_BACKEND_SKEGOX:
        backends_to_try: list[str] = [API_BACKEND_SKEGOX, API_BACKEND_AYLA]
    elif stored_backend == API_BACKEND_AYLA:
        backends_to_try = [API_BACKEND_AYLA, API_BACKEND_SKEGOX]
    else:
        backends_to_try = [API_BACKEND_SKEGOX, API_BACKEND_AYLA]

    coordinator: SharkIqUpdateCoordinator | SkegoxUpdateCoordinator | None = None
    devices: list[SharkDevice] = []

    for backend in backends_to_try:
        if backend == API_BACKEND_SKEGOX:
            coordinator, devices = await _try_skegox_setup(hass, config_entry, region)
        else:
            coordinator, devices = await _try_ayla_setup(hass, config_entry, region)

        if coordinator is not None:
            break

        # First backend failed and it was the previously stored one
        if backend == stored_backend:
            if backend == API_BACKEND_SKEGOX:
                LOGGER.warning("Skegox backend previously used but is no longer available -> Falling back to Ayla API..."
                )
            else:
                LOGGER.warning("Ayla backend previously used but is no longer available -> Trying Skegox API..."
                )

    if coordinator is None:
        LOGGER.error("Failed to connect to Shark IQ via any API backend")
        raise exceptions.ConfigEntryNotReady("Unable to connect to Shark IQ. Check credentials and region settings.")

    # Store the detected backend
    backend = API_BACKEND_SKEGOX if isinstance(coordinator, SkegoxUpdateCoordinator) else API_BACKEND_AYLA
    if config_entry.data.get(CONF_API_BACKEND) != backend:
        hass.config_entries.async_update_entry(config_entry, data={**config_entry.data, CONF_API_BACKEND: backend},)

    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True

# Disconnect from vacuum
# Skegox: Simply closes the aiohttp session.
# Ayla: Graceful sign-out, suppressing auth errors.
async def async_disconnect_or_timeout(coordinator: SharkIqUpdateCoordinator | SkegoxUpdateCoordinator) -> None:
    if isinstance(coordinator, SkegoxUpdateCoordinator):
        LOGGER.debug("Closing Skegox API session")
        await coordinator.skegox_api.close()
        return

    LOGGER.debug("Disconnecting from Ayla Api")
    async with asyncio.timeout(5):
        with suppress(SharkIqAuthError, SharkIqAuthExpiringError, SharkIqNotAuthedError):
            await coordinator.ayla_api.async_sign_out()

# Update options.
async def async_update_options(hass: HomeAssistant, config_entry: SharkIqConfigEntry) -> None:
    await hass.config_entries.async_reload(config_entry.entry_id)

# Unload a config entry.
async def async_unload_entry(hass: HomeAssistant, config_entry: SharkIqConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if unload_ok:
        with suppress(SharkIqAuthError):
            await async_disconnect_or_timeout(config_entry.runtime_data)

    return unload_ok