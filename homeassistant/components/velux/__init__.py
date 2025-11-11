"""Support for VELUX KLF 200 devices."""

from __future__ import annotations

from pyvlx import PyVLX, PyVLXException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, LOGGER, PLATFORMS

type VeluxConfigEntry = ConfigEntry[PyVLX]


async def async_setup_entry(hass: HomeAssistant, entry: VeluxConfigEntry) -> bool:
    """Set up the velux component."""
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]
    pyvlx = PyVLX(host=host, password=password)

    LOGGER.debug("Velux interface started")
    try:
        await pyvlx.load_scenes()
        await pyvlx.load_nodes()
    except PyVLXException as ex:
        LOGGER.exception("Can't connect to velux interface: %s", ex)
        return False

    device_identifier = (DOMAIN, f"gateway_{entry.entry_id}")
    entry.runtime_data = pyvlx

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={device_identifier},
        name="KLF 200 Gateway",
        manufacturer="Velux",
        model="KLF 200",
        hw_version=(
            str(pyvlx.klf200.version.hardwareversion) if pyvlx.klf200.version else None
        ),
        sw_version=(
            str(pyvlx.klf200.version.softwareversion) if pyvlx.klf200.version else None
        ),
    )

    async def on_hass_stop(event):
        """Close connection when hass stops."""
        LOGGER.debug("Velux interface terminated")
        await pyvlx.disconnect()

    async def async_reboot_gateway(service_call: ServiceCall) -> None:
        await pyvlx.reboot_gateway()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    hass.services.async_register(DOMAIN, "reboot_gateway", async_reboot_gateway)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VeluxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
