"""Support for AVM FRITZ!SmartHome devices."""
from __future__ import annotations

from datetime import timedelta

from pyfritzhome import Fritzhome, FritzhomeDevice, LoginError
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    TEMP_CELSIUS,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    CONF_CONNECTIONS,
    CONF_COORDINATOR,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .model import FritzExtraAttributes


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the AVM FRITZ!SmartHome platforms."""
    fritz = Fritzhome(
        host=entry.data[CONF_HOST],
        user=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await hass.async_add_executor_job(fritz.login)
    except LoginError as err:
        raise ConfigEntryAuthFailed from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_CONNECTIONS: fritz,
    }

    def _update_fritz_devices() -> dict[str, FritzhomeDevice]:
        """Update all fritzbox device data."""
        try:
            devices = fritz.get_devices()
        except requests.exceptions.HTTPError:
            # If the device rebooted, login again
            try:
                fritz.login()
            except requests.exceptions.HTTPError as ex:
                raise ConfigEntryAuthFailed from ex
            devices = fritz.get_devices()

        data = {}
        for device in devices:
            device.update()

            # assume device as unavailable, see #55799
            if (
                device.has_powermeter
                and device.present
                and hasattr(device, "voltage")
                and device.voltage <= 0
                and device.power <= 0
                and device.energy <= 0
            ):
                device.present = False

            data[device.ain] = device
        return data

    async def async_update_coordinator() -> dict[str, FritzhomeDevice]:
        """Fetch all device data."""
        return await hass.async_add_executor_job(_update_fritz_devices)

    hass.data[DOMAIN][entry.entry_id][
        CONF_COORDINATOR
    ] = coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{entry.entry_id}",
        update_method=async_update_coordinator,
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_config_entry_first_refresh()

    def _update_unique_id(entry: RegistryEntry) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if (
            entry.unit_of_measurement == TEMP_CELSIUS
            and "_temperature" not in entry.unique_id
        ):
            new_unique_id = f"{entry.unique_id}_temperature"
            LOGGER.info(
                "Migrating unique_id [%s] to [%s]", entry.unique_id, new_unique_id
            )
            return {"new_unique_id": new_unique_id}
        return None

    await async_migrate_entries(hass, entry.entry_id, _update_unique_id)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    def logout_fritzbox(event: Event) -> None:
        """Close connections to this fritzbox."""
        fritz.logout()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout_fritzbox)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the AVM FRITZ!SmartHome platforms."""
    fritz = hass.data[DOMAIN][entry.entry_id][CONF_CONNECTIONS]
    await hass.async_add_executor_job(fritz.logout)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FritzBoxEntity(CoordinatorEntity):
    """Basis FritzBox entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, FritzhomeDevice]],
        ain: str,
        entity_description: EntityDescription | None = None,
    ) -> None:
        """Initialize the FritzBox entity."""
        super().__init__(coordinator)

        self.ain = ain
        if entity_description is not None:
            self.entity_description = entity_description
            self._attr_name = f"{self.device.name} {entity_description.name}"
            self._attr_unique_id = f"{ain}_{entity_description.key}"
        else:
            self._attr_name = self.device.name
            self._attr_unique_id = ain

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.device.present

    @property
    def device(self) -> FritzhomeDevice:
        """Return device object from coordinator."""
        return self.coordinator.data[self.ain]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return {
            "name": self.device.name,
            "identifiers": {(DOMAIN, self.ain)},
            "manufacturer": self.device.manufacturer,
            "model": self.device.productname,
            "sw_version": self.device.fw_version,
        }

    @property
    def extra_state_attributes(self) -> FritzExtraAttributes:
        """Return the state attributes of the device."""
        return {
            ATTR_STATE_DEVICE_LOCKED: self.device.device_lock,
            ATTR_STATE_LOCKED: self.device.lock,
        }
