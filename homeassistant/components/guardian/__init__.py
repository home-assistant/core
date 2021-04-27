"""The Elexa Guardian integration."""
from __future__ import annotations

import asyncio

from aioguardian import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

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
    DATA_PAIRED_SENSOR_MANAGER,
    DATA_UNSUB_DISPATCHER_CONNECT,
    DOMAIN,
    LOGGER,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
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
        DATA_PAIRED_SENSOR_MANAGER: {},
        DATA_UNSUB_DISPATCHER_CONNECT: {},
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
    hass.data[DOMAIN][DATA_UNSUB_DISPATCHER_CONNECT][entry.entry_id] = []

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

    # Set up an object to evaluate each batch of paired sensor UIDs and add/remove
    # devices as appropriate:
    paired_sensor_manager = hass.data[DOMAIN][DATA_PAIRED_SENSOR_MANAGER][
        entry.entry_id
    ] = PairedSensorManager(hass, entry, client, api_lock)
    await paired_sensor_manager.async_process_latest_paired_sensor_uids()

    @callback
    def async_process_paired_sensor_uids():
        """Define a callback for when new paired sensor data is received."""
        hass.async_create_task(
            paired_sensor_manager.async_process_latest_paired_sensor_uids()
        )

    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
        API_SENSOR_PAIR_DUMP
    ].async_add_listener(async_process_paired_sensor_uids)

    # Set up all of the Guardian entity platforms:
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_CLIENT].pop(entry.entry_id)
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)
        hass.data[DOMAIN][DATA_LAST_SENSOR_PAIR_DUMP].pop(entry.entry_id)
        for unsub in hass.data[DOMAIN][DATA_UNSUB_DISPATCHER_CONNECT][entry.entry_id]:
            unsub()
        hass.data[DOMAIN][DATA_UNSUB_DISPATCHER_CONNECT].pop(entry.entry_id)

    return unload_ok


class PairedSensorManager:
    """Define an object that manages the addition/removal of paired sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: Client,
        api_lock: asyncio.Lock,
    ) -> None:
        """Initialize."""
        self._api_lock = api_lock
        self._client = client
        self._entry = entry
        self._hass = hass
        self._listeners = []
        self._paired_uids = set()

    async def async_pair_sensor(self, uid: str) -> None:
        """Add a new paired sensor coordinator."""
        LOGGER.debug("Adding paired sensor: %s", uid)

        self._paired_uids.add(uid)

        coordinator = self._hass.data[DOMAIN][DATA_COORDINATOR][self._entry.entry_id][
            API_SENSOR_PAIRED_SENSOR_STATUS
        ][uid] = GuardianDataUpdateCoordinator(
            self._hass,
            client=self._client,
            api_name=f"{API_SENSOR_PAIRED_SENSOR_STATUS}_{uid}",
            api_coro=lambda: self._client.sensor.paired_sensor_status(uid),
            api_lock=self._api_lock,
            valve_controller_uid=self._entry.data[CONF_UID],
        )
        await coordinator.async_request_refresh()

        async_dispatcher_send(
            self._hass,
            SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED.format(self._entry.data[CONF_UID]),
            uid,
        )

    async def async_process_latest_paired_sensor_uids(self) -> None:
        """Process a list of new UIDs."""
        try:
            uids = set(
                self._hass.data[DOMAIN][DATA_COORDINATOR][self._entry.entry_id][
                    API_SENSOR_PAIR_DUMP
                ].data["paired_uids"]
            )
        except KeyError:
            # Sometimes the paired_uids key can fail to exist; the user can't do anything
            # about it, so in this case, we quietly abort and return:
            return

        if uids == self._paired_uids:
            return

        old = self._paired_uids
        new = self._paired_uids = set(uids)

        tasks = [self.async_pair_sensor(uid) for uid in new.difference(old)]
        tasks += [self.async_unpair_sensor(uid) for uid in old.difference(new)]

        if tasks:
            await asyncio.gather(*tasks)

    async def async_unpair_sensor(self, uid: str) -> None:
        """Remove a paired sensor coordinator."""
        LOGGER.debug("Removing paired sensor: %s", uid)

        # Clear out objects related to this paired sensor:
        self._paired_uids.remove(uid)
        self._hass.data[DOMAIN][DATA_COORDINATOR][self._entry.entry_id][
            API_SENSOR_PAIRED_SENSOR_STATUS
        ].pop(uid)

        # Remove the paired sensor device from the device registry (which will
        # clean up entities and the entity registry):
        dev_reg = await self._hass.helpers.device_registry.async_get_registry()
        device = dev_reg.async_get_or_create(
            config_entry_id=self._entry.entry_id, identifiers={(DOMAIN, uid)}
        )
        dev_reg.async_remove_device(device.id)


class GuardianEntity(CoordinatorEntity):
    """Define a base Guardian entity."""

    def __init__(  # pylint: disable=super-init-not-called
        self, entry: ConfigEntry, kind: str, name: str, device_class: str, icon: str
    ) -> None:
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: "Data provided by Elexa"}
        self._available = True
        self._entry = entry
        self._device_class = device_class
        self._device_info = {"manufacturer": "Elexa"}
        self._icon = icon
        self._kind = kind
        self._name = name

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return self._device_class

    @property
    def device_info(self) -> dict:
        """Return device registry information for this entity."""
        return self._device_info

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

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


class PairedSensorEntity(GuardianEntity):
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

        self.coordinator = coordinator

        self._paired_sensor_uid = coordinator.data["uid"]

        self._device_info["identifiers"] = {(DOMAIN, self._paired_sensor_uid)}
        self._device_info["name"] = f"Guardian Paired Sensor {self._paired_sensor_uid}"
        self._device_info["via_device"] = (DOMAIN, self._entry.data[CONF_UID])

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Guardian Paired Sensor {self._paired_sensor_uid}: {self._name}"

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._paired_sensor_uid}_{self._kind}"

    async def async_added_to_hass(self) -> None:
        """Perform tasks when the entity is added."""
        self._async_update_from_latest_data()


class ValveControllerEntity(GuardianEntity):
    """Define a Guardian valve controller entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinators: dict[str, DataUpdateCoordinator],
        kind: str,
        name: str,
        device_class: str,
        icon: str,
    ) -> None:
        """Initialize."""
        super().__init__(entry, kind, name, device_class, icon)

        self.coordinators = coordinators

        self._device_info["identifiers"] = {(DOMAIN, self._entry.data[CONF_UID])}
        self._device_info[
            "name"
        ] = f"Guardian Valve Controller {self._entry.data[CONF_UID]}"
        self._device_info["model"] = self.coordinators[API_SYSTEM_DIAGNOSTICS].data[
            "firmware"
        ]

    @property
    def availabile(self) -> bool:
        """Return if entity is available."""
        return any(coordinator.last_update_success for coordinator in self.coordinators)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Guardian {self._entry.data[CONF_UID]}: {self._name}"

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._entry.data[CONF_UID]}_{self._kind}"

    async def _async_continue_entity_setup(self):
        """Perform additional, internal tasks when the entity is about to be added.

        This should be extended by Guardian platforms.
        """
        raise NotImplementedError

    @callback
    def async_add_coordinator_update_listener(self, api: str) -> None:
        """Add a listener to a DataUpdateCoordinator based on the API referenced."""
        self.async_on_remove(
            self.coordinators[api].async_add_listener(self._async_update_state_callback)
        )

    async def async_added_to_hass(self) -> None:
        """Perform tasks when the entity is added."""
        await self._async_continue_entity_setup()
        self.async_add_coordinator_update_listener(API_SYSTEM_DIAGNOSTICS)
        self._async_update_from_latest_data()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """

        # Ignore manual update requests if the entity is disabled
        if not self.enabled:
            return

        refresh_tasks = [
            coordinator.async_request_refresh() for coordinator in self.coordinators
        ]
        await asyncio.gather(*refresh_tasks)
