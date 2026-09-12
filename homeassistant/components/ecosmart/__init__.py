"""The ecosmart integration."""

from functools import partial

from aioecosmart import (
    EcosmartAuthError,
    EcosmartClient,
    EcosmartError,
    EcosmartRateLimitError,
    Forecast,
    Spot,
)

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    FORECAST_HORIZON_HOURS,
    FORECAST_SCAN_INTERVAL,
    LOGGER,
    SPOT_SCAN_INTERVAL,
)
from .coordinator import EcosmartConfigEntry, EcosmartCoordinator, EcosmartRuntimeData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EcosmartConfigEntry) -> bool:
    """Set up ecosmart from a config entry."""
    client = EcosmartClient(entry.data[CONF_API_KEY], async_get_clientsession(hass))

    try:
        identity = await client.me()
    except EcosmartAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except EcosmartRateLimitError as err:
        # ConfigEntryNotReady has no retry_after support; HA retries in ~5s.
        # Do not claim a delay the framework will not honour.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="rate_limited_setup",
        ) from err
    except EcosmartError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    LOGGER.debug(
        "ecosmart key %s covers %s ICP(s) with a budget of %s requests/minute",
        identity.key_prefix,
        len(identity.allowed_icps),
        identity.rate_limit_per_minute,
    )

    # Prices are published per grid exit point, so several ICPs behind the same
    # one cost a single request between them.
    pocs = sorted({scope.poc for scope in identity.allowed_icps})

    spot_coordinator = EcosmartCoordinator[Spot](
        hass,
        entry,
        pocs,
        name="spot price",
        update_interval=SPOT_SCAN_INTERVAL,
        fetch=client.spot,
    )
    forecast_coordinator = EcosmartCoordinator[Forecast](
        hass,
        entry,
        pocs,
        name="price forecast",
        update_interval=FORECAST_SCAN_INTERVAL,
        fetch=partial(client.forecast, hours=FORECAST_HORIZON_HOURS),
    )
    await spot_coordinator.async_config_entry_first_refresh()
    await forecast_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = EcosmartRuntimeData(
        client=client,
        identity=identity,
        spot_coordinator=spot_coordinator,
        forecast_coordinator=forecast_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcosmartConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
