"""The Elexa Guardian integration."""
import asyncio
from typing import Dict

from aioguardian import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    API_SENSOR_PAIR_DUMP,
    API_SENSOR_PAIRED_SENSOR_STATUS,
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_VALVE_STATUS,
    API_WIFI_STATUS,
    CONF_UID,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)
from .util import GuardianDataUpdateCoordinator

DATA_LAST_SENSOR_PAIR_DUMP = "last_sensor_pair_dump"

PLATFORMS = ["binary_sensor", "sensor", "switch"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Elexa Guardian component."""
    hass.data[DOMAIN] = {
        DATA_CLIENT: {},
        DATA_COORDINATOR: {},
        DATA_LAST_SENSOR_PAIR_DUMP: {},
    }
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elexa Guardian from a config entry."""
    client = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id] = Client(
        entry.data[CONF_IP_ADDRESS], port=entry.data[CONF_PORT]
    )
    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id] = {
        API_SENSOR_PAIRED_SENSOR_STATUS: {}
    }

    # The valve controller's UDP-based API can't handle concurrent requests very well,
    # so we use a lock to ensure that only one API request is reaching it at a time:
    api_lock = asyncio.Lock()

    # Set up DataUpdateCoordinators for the valve controller:
    init_valve_controller_tasks = []
    for api, api_coro in [
        (API_SENSOR_PAIR_DUMP, client.sensor.pair_dump),
        (API_SYSTEM_DIAGNOSTICS, client.system.diagnostics),
        (API_SYSTEM_ONBOARD_SENSOR_STATUS, client.system.onboard_sensor_status),
        (API_VALVE_STATUS, client.valve.status),
        (API_WIFI_STATUS, client.wifi.status),
    ]:
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
            api
        ] = GuardianDataUpdateCoordinator(
            hass,
            client=client,
            api_name=api,
            api_coro=api_coro,
            api_lock=api_lock,
            valve_controller_uid=entry.data[CONF_UID],
        )
        init_valve_controller_tasks.append(coordinator.async_refresh())

    await asyncio.gather(*init_valve_controller_tasks)

    # Set up DataUpdateCoordinators for any paired sensors:
    init_paired_sensor_tasks = []
    for uid in hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
        API_SENSOR_PAIR_DUMP
    ].data["paired_uids"]:
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
            API_SENSOR_PAIRED_SENSOR_STATUS
        ][uid] = GuardianDataUpdateCoordinator(
            hass,
            client=client,
            api_name=f"{API_SENSOR_PAIRED_SENSOR_STATUS}_{uid}",
            api_coro=lambda uid=uid: client.sensor.paired_sensor_status(uid),
            api_lock=api_lock,
            valve_controller_uid=entry.data[CONF_UID],
        )
        init_paired_sensor_tasks.append(coordinator.async_refresh())

    await asyncio.gather(*init_paired_sensor_tasks)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unloa_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_CLIENT].pop(entry.entry_id)
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)
        hass.data[DOMAIN][DATA_LAST_SENSOR_PAIR_DUMP].pop(entry.entry_id)

    return unload_ok


class GuardianEntity(Entity):
    """Define a base Guardian entity."""

    def __init__(
        self, entry: ConfigEntry, kind: str, name: str, device_class: str, icon: str
    ) -> None:
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: "Data provided by Elexa"}
        self._available = True
        self._device_class = device_class
        self._icon = icon
        self._kind = kind
        self._name = name
        self._valve_controller_uid = entry.data[CONF_UID]

        self._device_info = {
            "identifiers": {(DOMAIN, self._valve_controller_uid)},
            "manufacturer": "Elexa",
            "name": f"Guardian {self._valve_controller_uid}",
        }

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return self._device_class

    @property
    def device_info(self) -> dict:
        """Return device registry information for this entity."""
        return self._device_info

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    async def _async_internal_added_to_hass(self):
        """Perform additional, internal tasks when the entity is about to be added.

        This should be extended by Guardian platforms.
        """
        raise NotImplementedError

    @callback
    def _async_update_from_latest_data(self):
        """Update the entity.

        This should be extended by Guardian platforms.
        """
        raise NotImplementedError

    @callback
    def _async_update_state_callback(self):
        """Update the entity's state."""
        self._async_update_from_latest_data()
        self.async_write_ha_state()


class PairedSensorEntity(Entity):
    """Define a Guardian paired sensor entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        kind: str,
        name: str,
        device_class: str,
        icon: str,
    ) -> None:
        """Initialize."""
        super().__init__(entry, kind, name, device_class, icon)

        self._coordinator = coordinator
        self._paired_sensor_uid = coordinator.data["uid"]

        self._device_info["via_device"] = (DOMAIN, self._valve_controller_uid)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Guardian Paired Sensor {self._paired_sensor_uid}: {self._name}"

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._paired_sensor_uid}_{self._kind}"


class ValveControllerEntity(GuardianEntity):
    """Define a Guardian valve controller entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinators: Dict[str, DataUpdateCoordinator],
        kind: str,
        name: str,
        device_class: str,
        icon: str,
    ) -> None:
        """Initialize."""
        super().__init__(entry, kind, name, device_class, icon)

        self._coordinators = coordinators

        self._device_info["model"] = self._coordinators[API_SYSTEM_DIAGNOSTICS].data[
            "firmware"
        ]

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Guardian {self._valve_controller_uid}: {self._name}"

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._valve_controller_uid}_{self._kind}"

    @callback
    def async_add_coordinator_update_listener(self, api: str) -> None:
        """Add a listener to a DataUpdateCoordinator based on the API referenced."""
        self.async_on_remove(
            self._coordinators[api].async_add_listener(
                self._async_update_state_callback
            )
        )

    async def async_added_to_hass(self) -> None:
        """Perform tasks when the entity is added."""
        await self._async_internal_added_to_hass()
        self.async_add_coordinator_update_listener(API_SYSTEM_DIAGNOSTICS)
        self._async_update_from_latest_data()
