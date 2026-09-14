"""The vizio component."""

from vizaio import (
    DeviceType,
    Vizio,
    VizioError,
    async_classify_device,
    async_resolve_host,
)

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_APPS,
    CONF_DEVICE_TYPE,
    CONF_VOLUME_STEP,
    DEFAULT_TIMEOUT,
    DOMAIN,
    VIZIO_DEVICE_CLASSES,
)
from .coordinator import (
    VizioAppsDataUpdateCoordinator,
    VizioConfigEntry,
    VizioDeviceCoordinator,
    VizioRuntimeData,
)
from .services import async_setup_services

DATA_APPS: HassKey[VizioAppsDataUpdateCoordinator] = HassKey(f"{DOMAIN}_apps")

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: VizioConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version == 1 and entry.minor_version == 1:
        # Settings imported from YAML were stored in data; they belong in options
        data = dict(entry.data)
        options = dict(entry.options)
        if (volume_step := data.pop(CONF_VOLUME_STEP, None)) is not None:
            options.setdefault(CONF_VOLUME_STEP, volume_step)
        if apps := dict(data.pop(CONF_APPS, {})):
            include_or_exclude = {
                key: apps.pop(key)
                for key in (CONF_INCLUDE, CONF_EXCLUDE)
                if key in apps
            }
            if include_or_exclude:
                options.setdefault(CONF_APPS, include_or_exclude)
            if apps:
                data[CONF_APPS] = apps
        hass.config_entries.async_update_entry(
            entry, data=data, options=options, minor_version=2
        )
    return True


async def _async_resolve_device_type(
    hass: HomeAssistant, entry: VizioConfigEntry
) -> DeviceType:
    """Resolve the vizaio device type for a config entry.

    Speaker entries are classified once to distinguish battery-powered
    Crave models (own volume scale, battery sensors) from soundbars, and
    the result is persisted on the entry. Entries from before this key
    existed are classified here as well.
    """
    if (stored := entry.data.get(CONF_DEVICE_TYPE)) is not None:
        return DeviceType(stored)

    device_class = entry.data[CONF_DEVICE_CLASS]
    fallback: DeviceType = VIZIO_DEVICE_CLASSES[device_class]
    if device_class != MediaPlayerDeviceClass.SPEAKER:
        return fallback

    try:
        device_type = await async_classify_device(
            entry.data[CONF_HOST],
            session=async_get_clientsession(hass, False),
        )
    except VizioError:
        # Device unreachable; use the generic profile and retry next setup
        return fallback
    if device_type is DeviceType.TV:
        # Classification contradicts the configured device class; trust the user
        return fallback

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_DEVICE_TYPE: device_type.value}
    )
    return device_type


async def async_setup_entry(hass: HomeAssistant, entry: VizioConfigEntry) -> bool:
    """Load the saved entities."""
    host = entry.data[CONF_HOST]
    token = entry.data.get(CONF_ACCESS_TOKEN)
    device_class = entry.data[CONF_DEVICE_CLASS]

    # Entries created before the host was stored with a port need one probed
    # and persisted, otherwise every request targets port 443. Resolving is a
    # no-op for a host that already has one.
    try:
        resolved_host = await async_resolve_host(
            host,
            session=async_get_clientsession(hass, False),
            timeout=DEFAULT_TIMEOUT,
        )
    except VizioError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_determine_port",
            translation_placeholders={"host": host},
        ) from err
    if resolved_host != host:
        host = resolved_host
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_HOST: host}
        )

    # Create device
    device = Vizio(
        host,
        device_type=await _async_resolve_device_type(hass, entry),
        auth_token=token,
        session=async_get_clientsession(hass, False),
        timeout=DEFAULT_TIMEOUT,
    )

    # Create device coordinator
    device_coordinator = VizioDeviceCoordinator(hass, entry, device)
    await device_coordinator.async_config_entry_first_refresh()

    # Create apps coordinator for TVs (shared across entries)
    if device_class == MediaPlayerDeviceClass.TV and DATA_APPS not in hass.data:
        apps_coordinator = VizioAppsDataUpdateCoordinator(hass, Store(hass, 1, DOMAIN))
        await apps_coordinator.async_setup()
        hass.data[DATA_APPS] = apps_coordinator
        await apps_coordinator.async_refresh()

    entry.runtime_data = VizioRuntimeData(
        device_coordinator=device_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VizioConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clean up apps coordinator if no TV entries remain
    if unload_ok and not any(
        e.data[CONF_DEVICE_CLASS] == MediaPlayerDeviceClass.TV
        for e in hass.config_entries.async_loaded_entries(DOMAIN)
        if e.entry_id != entry.entry_id
    ):
        if apps_coordinator := hass.data.pop(DATA_APPS, None):
            await apps_coordinator.async_shutdown()

    return unload_ok
