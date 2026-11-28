"""The Rexense integration."""

from dataclasses import dataclass

from aiorexense import (
    RexenseAuthenticationError,
    RexenseError,
    RexenseGateway,
    UnsupportedTaxonomyError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, MANUFACTURER

PLATFORMS = [Platform.SWITCH]


@dataclass
class RexenseData:
    """Runtime connection and Home Assistant gateway registration."""

    gateway: RexenseGateway
    gateway_device_id: str


type RexenseConfigEntry = ConfigEntry[RexenseData]


async def async_setup_entry(hass: HomeAssistant, entry: RexenseConfigEntry) -> None:
    """Connect to a gateway and set up its switches."""
    gateway = RexenseGateway(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_API_KEY],
        use_ssl=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        expected_gateway_id=entry.unique_id,
    )
    try:
        await gateway.async_start()
    except RexenseAuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except UnsupportedTaxonomyError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="unsupported_gateway"
        ) from err
    except RexenseError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    try:
        system = gateway.gateway.get("system", {})
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, str(gateway.unique_id))},
            name=f"Rexense {system.get('model', 'gateway')}",
            manufacturer=MANUFACTURER,
            model=system.get("model"),
            sw_version=system.get("sw_version"),
            serial_number=system.get("sn"),
        )
        entry.runtime_data = RexenseData(gateway, device.id)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await gateway.async_stop()
        raise

    async def async_stop(event: Event) -> None:
        """Close the connection before Home Assistant closes its shared session."""
        await gateway.async_stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)
    )


async def async_unload_entry(hass: HomeAssistant, entry: RexenseConfigEntry) -> None:
    """Unload the switches and close the gateway connection."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.gateway.async_stop()
