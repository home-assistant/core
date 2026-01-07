"""Support for VELUX KLF 200 devices."""

from __future__ import annotations

from pyvlx import PyVLX, PyVLXException

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, PLATFORMS

type VeluxConfigEntry = ConfigEntry[PyVLX]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Velux component."""

    async def async_reboot_gateway(service_call: ServiceCall) -> None:
        """Reboot the gateway (deprecated - use button entity instead)."""
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_reboot_service",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_reboot_service",
            breaks_in_ha_version="2026.6.0",
        )

        # Find a loaded config entry to get the PyVLX instance
        # We assume only one gateway is set up or we just reboot the first one found
        # (this is no change to the previous behavior, the alternative would be to reboot all)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED:
                try:
                    await entry.runtime_data.reboot_gateway()
                except (OSError, PyVLXException) as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="reboot_failed",
                    ) from err
                else:
                    return

        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_gateway_loaded",
        )

    hass.services.async_register(DOMAIN, "reboot_gateway", async_reboot_gateway)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: VeluxConfigEntry) -> bool:
    """Set up the velux component."""
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]
    pyvlx = PyVLX(host=host, password=password)

    LOGGER.debug("Setting up Velux gateway %s", host)
    try:
        LOGGER.debug("Retrieving scenes from %s", host)
        await pyvlx.load_scenes()
        LOGGER.debug("Retrieving nodes from %s", host)
        await pyvlx.load_nodes()
    except (OSError, PyVLXException) as ex:
        # Since pyvlx raises the same exception for auth and connection errors,
        # we need to check the exception message to distinguish them.
        # Ultimately this should be fixed in pyvlx to raise specialized exceptions,
        # right now it's been a while since the last pyvlx release, so we do this workaround here.
        if (
            isinstance(ex, PyVLXException)
            and ex.description == "Login to KLF 200 failed, check credentials"
        ):
            raise ConfigEntryAuthFailed(
                f"Invalid authentication for Velux gateway at {host}"
            ) from ex

        # Defer setup and retry later as the bridge is not ready/available
        raise ConfigEntryNotReady(
            f"Unable to connect to Velux gateway at {host}. "
            "If connection continues to fail, try power-cycling the gateway device."
        ) from ex

    LOGGER.debug("Velux connection to %s successful", host)
    entry.runtime_data = pyvlx

    connections = None
    if (mac := entry.data.get(CONF_MAC)) is not None:
        connections = {(dr.CONNECTION_NETWORK_MAC, mac)}

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"gateway_{entry.entry_id}")},
        name="KLF 200 Gateway",
        manufacturer="Velux",
        model="KLF 200",
        hw_version=(
            str(pyvlx.klf200.version.hardwareversion) if pyvlx.klf200.version else None
        ),
        sw_version=(
            str(pyvlx.klf200.version.softwareversion) if pyvlx.klf200.version else None
        ),
        connections=connections,
    )

    async def on_hass_stop(event):
        """Close connection when hass stops."""
        LOGGER.debug("Velux interface terminated")
        await pyvlx.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VeluxConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Disconnect from gateway only after platforms are successfully unloaded.
        # Disconnecting will reboot the gateway in the pyvlx library, which is needed to allow new
        # connections to be made later.
        await entry.runtime_data.disconnect()
    return unload_ok
