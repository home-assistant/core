"""Support for VELUX KLF 200 devices."""

from pyvlx import PyVLX, PyVLXException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN, LOGGER, PLATFORMS, PYVLX_FROM_CONFIG_FLOW

type VeluxConfigEntry = ConfigEntry[PyVLX]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: VeluxConfigEntry) -> bool:
    """Set up the velux component."""
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]

    # Prefer the already-connected instance passed from the config flow so that
    # we do not force a disconnect/reboot between connection validation and setup.
    # Falls back to creating a fresh instance on HA restart or reload.
    pyvlx: PyVLX | None = hass.data.get(PYVLX_FROM_CONFIG_FLOW, {}).pop(host, None)
    if pyvlx is None:
        pyvlx = PyVLX(host=host, password=password)

    try:
        LOGGER.debug("Ensuring connection to Velux gateway %s", host)
        await pyvlx.ensure_connected()
        LOGGER.debug("Retrieving scenes from %s", host)
        await pyvlx.load_scenes()
        LOGGER.debug("Retrieving nodes from %s", host)
        await pyvlx.load_nodes()
    except (OSError, PyVLXException) as ex:
        # Since pyvlx raises the same exception for auth and connection errors,
        # we need to check the exception message to distinguish them.
        # Ultimately this should be fixed in pyvlx to raise specialized exceptions,
        # right now it's been a while since the last pyvlx
        # release, so we do this workaround here.
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

    async def on_hass_stop(_: Event) -> None:
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
        # Disconnecting will reboot the gateway in the pyvlx
        # library, which is needed to allow new
        # connections to be made later.
        await entry.runtime_data.disconnect()
    return unload_ok
