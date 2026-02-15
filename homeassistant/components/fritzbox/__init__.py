"""Support for AVM FRITZ!SmartHome devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from requests.exceptions import ConnectionError as RequestConnectionError, HTTPError
from yarl import URL

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries

from .const import DEFAULT_VERIFY_SSL, DOMAIN, LOGGER, PLATFORMS
from .coordinator import FritzboxConfigEntry, FritzboxDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: FritzboxConfigEntry) -> bool:
    """Set up the AVM FRITZ!SmartHome platforms."""

    def _update_unique_id(entry: RegistryEntry) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if (
            entry.unit_of_measurement == UnitOfTemperature.CELSIUS
            and "_temperature" not in entry.unique_id
        ):
            new_unique_id = f"{entry.unique_id}_temperature"
            LOGGER.debug(
                "Migrating unique_id [%s] to [%s]", entry.unique_id, new_unique_id
            )
            return {"new_unique_id": new_unique_id}

        if entry.domain == BINARY_SENSOR_DOMAIN and "_" not in entry.unique_id:
            new_unique_id = f"{entry.unique_id}_alarm"
            LOGGER.debug(
                "Migrating unique_id [%s] to [%s]", entry.unique_id, new_unique_id
            )
            return {"new_unique_id": new_unique_id}
        return None

    await async_migrate_entries(hass, entry.entry_id, _update_unique_id)

    coordinator = FritzboxDataUpdateCoordinator(hass, entry)
    await coordinator.async_setup()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def logout_fritzbox(event: Event) -> None:
        """Close connections to this fritzbox."""
        coordinator.fritz.logout()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout_fritzbox)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FritzboxConfigEntry) -> bool:
    """Unloading the AVM FRITZ!SmartHome platforms."""
    try:
        await hass.async_add_executor_job(entry.runtime_data.fritz.logout)
    except (RequestConnectionError, HTTPError) as ex:
        LOGGER.debug("logout failed with '%s', anyway continue with unload", ex)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: FritzboxConfigEntry
) -> bool:
    """Migrate old config entry to a new format."""
    LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )
    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new_data = {**config_entry.data}
        if config_entry.minor_version < 2:
            LOGGER.debug("Migrate config entry data to URL based configuration")
            if "://" not in config_entry.data[CONF_HOST]:
                host = URL().build(
                    scheme="http",
                    host=config_entry.data[CONF_HOST],
                )
                port = 80
            else:
                host = config_entry.data[CONF_HOST]
                url = URL(config_entry.data[CONF_HOST])
                if TYPE_CHECKING:
                    assert isinstance(url.port, int)
                port = url.port

            new_data = {
                **config_entry.data,
                CONF_HOST: str(host),
                CONF_PORT: port,
                CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
            }

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=1, minor_version=2
        )

    LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: FritzboxConfigEntry, device: DeviceEntry
) -> bool:
    """Remove Fritzbox config entry from a device."""
    coordinator = entry.runtime_data

    for identifier in device.identifiers:
        if identifier[0] == DOMAIN and (
            identifier[1] in coordinator.data.devices
            or identifier[1] in coordinator.data.templates
        ):
            return False

    return True
