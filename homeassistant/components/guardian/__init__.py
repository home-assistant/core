"""The Elexa Guardian integration."""
import asyncio
from typing import Any, Callable, Dict

from aioguardian import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_entries_for_device
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
    LOGGER,
    SIGNAL_ADD_PAIRED_SENSOR,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
    SIGNAL_REMOVE_PAIRED_SENSOR,
)
from .util import GuardianDataUpdateCoordinator

DATA_LAST_SENSOR_PAIR_DUMP = "last_sensor_pair_dump"
DATA_UNSUB_DISPATCHER_CONNECTS = "unsub_dispatcher_connects"

SIGNAL_NEW_SENSOR_PAIR_DUMP = "guardian_new_sensor_pair_dump_{0}"

PLATFORMS = ["binary_sensor", "sensor", "switch"]


@callback
def async_register_dispatcher_connect(
    hass: HomeAssistant, entry: ConfigEntry, signal: str, target: Callable[..., Any]
) -> None:
    """Store a new dispatcher connect unsub handler."""
    hass.data[DOMAIN][DATA_UNSUB_DISPATCHER_CONNECTS][entry.entry_id].append(
        async_dispatcher_connect(hass, signal, target)
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Elexa Guardian component."""
    hass.data[DOMAIN] = {
        DATA_CLIENT: {},
        DATA_COORDINATOR: {},
        DATA_LAST_SENSOR_PAIR_DUMP: {},
        DATA_UNSUB_DISPATCHER_CONNECTS: {},
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
    hass.data[DOMAIN][DATA_UNSUB_DISPATCHER_CONNECTS][entry.entry_id] = []

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
    paired_sensor_manager = PairedSensorManager(hass, entry, client, api_lock)
    await paired_sensor_manager.async_init()

    @callback
    def async_new_sensor_pair_dump():
        """Define a callback for when new paired sensor data is received."""
        async_dispatcher_send(
            hass, SIGNAL_NEW_SENSOR_PAIR_DUMP.format(entry.data[CONF_UID])
        )

    # When the sensor_pair_dump API completes, send a signal (via the dispatcher) to the
    # PairedSensorManager so it can process any paired sensor addition/removal:
    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
        API_SENSOR_PAIR_DUMP
    ].async_add_listener(async_new_sensor_pair_dump)

    # Set up all of the Guardian entity platforms:
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
        for async_unsub_dispatcher_connect in hass.data[DOMAIN][
            DATA_UNSUB_DISPATCHER_CONNECTS
        ][entry.entry_id]:
            async_unsub_dispatcher_connect()
        hass.data[DOMAIN][DATA_UNSUB_DISPATCHER_CONNECTS].pop(entry.entry_id)

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
        self._paired_uids = set()

    async def async_init(self) -> None:
        """Perform post-creation initialization."""

        for signal_template, target in [
            (SIGNAL_ADD_PAIRED_SENSOR, self.async_pair_sensor),
            (SIGNAL_NEW_SENSOR_PAIR_DUMP, self.async_process_latest_paired_sensor_uids),
            (SIGNAL_REMOVE_PAIRED_SENSOR, self.async_unpair_sensor),
        ]:
            async_register_dispatcher_connect(
                self._hass,
                self._entry,
                signal_template.format(self._entry.data[CONF_UID]),
                target,
            )

        await self.async_process_latest_paired_sensor_uids()

    async def async_pair_sensor(self, uid: str) -> None:
        """Add a new paired sensor coordinator."""
        LOGGER.info("Adding paired sensor: %s", uid)

        coordinator = self._hass.data[DOMAIN][DATA_COORDINATOR][self._entry.entry_id][
            API_SENSOR_PAIRED_SENSOR_STATUS
        ][uid] = GuardianDataUpdateCoordinator(
            self._hass,
            client=self._client,
            api_name=f"{API_SENSOR_PAIRED_SENSOR_STATUS}_{uid}",
            api_coro=lambda uid=uid: self._client.sensor.paired_sensor_status(uid),
            api_lock=self._api_lock,
            valve_controller_uid=self._entry.data[CONF_UID],
        )

        await coordinator.async_refresh()

        self._paired_uids.add(uid)

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

        to_add = new.difference(old)
        to_remove = old.difference(new)

        if to_add:
            add_tasks = [self.async_pair_sensor(uid) for uid in to_add]
            await asyncio.gather(*add_tasks)

        for uid in to_remove:
            self.async_unpair_sensor(uid)

    @callback
    def async_unpair_sensor(self, uid: str) -> None:
        """Remove a paired sensor coordinator."""
        LOGGER.info("Removing paired sensor: %s", uid)

        self._paired_uids.remove(uid)

        self._hass.data[DOMAIN][DATA_COORDINATOR][self._entry.entry_id][
            API_SENSOR_PAIRED_SENSOR_STATUS
        ].pop(uid)


class GuardianEntity(Entity):
    """Define a base Guardian entity."""

    def __init__(
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

        self._coordinator = coordinator
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
        self.async_on_remove(
            self._coordinator.async_add_listener(self._async_update_state_callback)
        )

        async def async_remove(uid: str):
            """Remove the entity from the registry and the state machine.

            Also removes the associated paired sensor device if this is the last entity.
            """
            if uid != self._paired_sensor_uid:
                return

            ent_reg = await self.hass.helpers.entity_registry.async_get_registry()
            ent_entry = ent_reg.async_get(self.entity_id)
            if not ent_entry:
                await self.async_remove()
                return

            dev_reg = await self.hass.helpers.device_registry.async_get_registry()
            dev_ent = dev_reg.async_get(ent_entry.device_id)
            if not dev_ent:
                ent_reg.async_remove(self.entity_id)
                return

            if len(async_entries_for_device(ent_reg, ent_entry.device_id)) == 1:
                dev_reg.async_remove_device(dev_ent.id)
                return

            ent_reg.async_remove(self.entity_id)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_REMOVE_PAIRED_SENSOR.format(self._entry.data[CONF_UID]),
                async_remove,
            )
        )

        self._async_update_from_latest_data()


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

        self._device_info["identifiers"] = {(DOMAIN, self._entry.data[CONF_UID])}
        self._device_info[
            "name"
        ] = f"Guardian Valve Controller {self._entry.data[CONF_UID]}"
        self._device_info["model"] = self._coordinators[API_SYSTEM_DIAGNOSTICS].data[
            "firmware"
        ]

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Guardian {self._entry.data[CONF_UID]}: {self._name}"

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._entry.data[CONF_UID]}_{self._kind}"

    async def _async_internal_added_to_hass(self):
        """Perform additional, internal tasks when the entity is about to be added.

        This should be extended by Guardian platforms.
        """
        raise NotImplementedError

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
