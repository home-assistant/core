"""The Elexa Guardian integration."""
import asyncio
from datetime import timedelta

from aioguardian import Client
from aioguardian.commands.device import (
    DEFAULT_FIRMWARE_UPGRADE_FILENAME,
    DEFAULT_FIRMWARE_UPGRADE_PORT,
    DEFAULT_FIRMWARE_UPGRADE_URL,
)
from aioguardian.errors import GuardianError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_FILENAME,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_URL,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import (
    async_register_admin_service,
    verify_domain_control,
)

from .const import (
    CONF_UID,
    DATA_CLIENT,
    DATA_DIAGNOSTICS,
    DATA_PAIR_DUMP,
    DATA_PING,
    DATA_SENSOR_STATUS,
    DATA_VALVE_STATUS,
    DATA_WIFI_STATUS,
    DOMAIN,
    LOGGER,
    SENSOR_KIND_AP_INFO,
    SENSOR_KIND_LEAK_DETECTED,
    SENSOR_KIND_TEMPERATURE,
    SWITCH_KIND_VALVE,
    TOPIC_UPDATE,
)

DATA_ENTITY_TYPE_MAP = {
    SENSOR_KIND_AP_INFO: DATA_WIFI_STATUS,
    SENSOR_KIND_LEAK_DETECTED: DATA_SENSOR_STATUS,
    SENSOR_KIND_TEMPERATURE: DATA_SENSOR_STATUS,
    SWITCH_KIND_VALVE: DATA_VALVE_STATUS,
}

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

PLATFORMS = ["binary_sensor", "sensor", "switch"]

SERVICE_UPGRADE_FIRMWARE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_URL, default=DEFAULT_FIRMWARE_UPGRADE_URL): cv.url,
        vol.Optional(CONF_PORT, default=DEFAULT_FIRMWARE_UPGRADE_PORT): cv.port,
        vol.Optional(
            CONF_FILENAME, default=DEFAULT_FIRMWARE_UPGRADE_FILENAME
        ): cv.string,
    }
)


@callback
def async_get_api_category(entity_kind: str):
    """Get the API data category to which an entity belongs."""
    return DATA_ENTITY_TYPE_MAP.get(entity_kind)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Elexa Guardian component."""
    hass.data[DOMAIN] = {DATA_CLIENT: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Elexa Guardian from a config entry."""
    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    guardian = Guardian(hass, entry)
    await guardian.async_update()
    hass.data[DOMAIN][DATA_CLIENT][entry.entry_id] = guardian

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    @_verify_domain_control
    async def disable_ap(call):
        """Disable the device's onboard access point."""
        try:
            async with guardian.client:
                await guardian.client.device.wifi_disable_ap()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    @_verify_domain_control
    async def enable_ap(call):
        """Enable the device's onboard access point."""
        try:
            async with guardian.client:
                await guardian.client.device.wifi_enable_ap()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    @_verify_domain_control
    async def reboot(call):
        """Reboot the device."""
        try:
            async with guardian.client:
                await guardian.client.device.reboot()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    @_verify_domain_control
    async def reset_valve_diagnostics(call):
        """Fully reset system motor diagnostics."""
        try:
            async with guardian.client:
                await guardian.client.valve.valve_reset()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    @_verify_domain_control
    async def upgrade_firmware(call):
        """Upgrade the device firmware."""
        try:
            async with guardian.client:
                await guardian.client.device.upgrade_firmware(
                    url=call.data[CONF_URL],
                    port=call.data[CONF_PORT],
                    filename=call.data[CONF_FILENAME],
                )
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    for service, method, schema in [
        ("disable_ap", disable_ap, None),
        ("enable_ap", enable_ap, None),
        ("reboot", reboot, None),
        ("reset_valve_diagnostics", reset_valve_diagnostics, None),
        ("upgrade_firmware", upgrade_firmware, SERVICE_UPGRADE_FIRMWARE_SCHEMA),
    ]:
        async_register_admin_service(hass, DOMAIN, service, method, schema=schema)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
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

    return unload_ok


class Guardian:
    """Define a class to communicate with the Guardian device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize."""
        self._async_cancel_time_interval_listener = None
        self._hass = hass
        self.client = Client(entry.data[CONF_IP_ADDRESS])
        self.data = {}
        self.uid = entry.data[CONF_UID]

        self._api_coros = {
            DATA_DIAGNOSTICS: self.client.device.diagnostics,
            DATA_PAIR_DUMP: self.client.sensor.pair_dump,
            DATA_PING: self.client.device.ping,
            DATA_SENSOR_STATUS: self.client.sensor.sensor_status,
            DATA_VALVE_STATUS: self.client.valve.valve_status,
            DATA_WIFI_STATUS: self.client.device.wifi_status,
        }

        self._api_category_count = {
            DATA_SENSOR_STATUS: 0,
            DATA_VALVE_STATUS: 0,
            DATA_WIFI_STATUS: 0,
        }

        self._api_lock = asyncio.Lock()

    async def _async_get_data_from_api(self, api_category: str):
        """Update and save data for a particular API category."""
        if self._api_category_count.get(api_category) == 0:
            return

        try:
            result = await self._api_coros[api_category]()
        except GuardianError as err:
            LOGGER.error("Error while fetching %s data: %s", api_category, err)
            self.data[api_category] = {}
        else:
            self.data[api_category] = result["data"]

    async def _async_update_listener_action(self, _):
        """Define an async_track_time_interval action to update data."""
        await self.async_update()

    @callback
    def async_deregister_api_interest(self, sensor_kind: str):
        """Decrement the number of entities with data needs from an API category."""
        # If this deregistration should leave us with no registration at all, remove the
        # time interval:
        if sum(self._api_category_count.values()) == 0:
            if self._async_cancel_time_interval_listener:
                self._async_cancel_time_interval_listener()
                self._async_cancel_time_interval_listener = None
            return

        api_category = async_get_api_category(sensor_kind)
        if api_category:
            self._api_category_count[api_category] -= 1

    async def async_register_api_interest(self, sensor_kind: str):
        """Increment the number of entities with data needs from an API category."""
        # If this is the first registration we have, start a time interval:
        if not self._async_cancel_time_interval_listener:
            self._async_cancel_time_interval_listener = async_track_time_interval(
                self._hass, self._async_update_listener_action, DEFAULT_SCAN_INTERVAL,
            )

        api_category = async_get_api_category(sensor_kind)

        if not api_category:
            return

        self._api_category_count[api_category] += 1

        # If a sensor registers interest in a particular API call and the data doesn't
        # exist for it yet, make the API call and grab the data:
        async with self._api_lock:
            if api_category not in self.data:
                async with self.client:
                    await self._async_get_data_from_api(api_category)

    async def async_update(self):
        """Get updated data from the device."""
        async with self.client:
            tasks = [
                self._async_get_data_from_api(api_category)
                for api_category in self._api_coros
            ]

            await asyncio.gather(*tasks)

        LOGGER.debug("Received new data: %s", self.data)
        async_dispatcher_send(self._hass, TOPIC_UPDATE.format(self.uid))


class GuardianEntity(Entity):
    """Define a base Guardian entity."""

    def __init__(
        self, guardian: Guardian, kind: str, name: str, device_class: str, icon: str
    ):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: "Data provided by Elexa"}
        self._available = True
        self._device_class = device_class
        self._guardian = guardian
        self._icon = icon
        self._kind = kind
        self._name = name

    @property
    def available(self):
        """Return whether the entity is available."""
        return bool(self._guardian.data[DATA_PING])

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._guardian.uid)},
            "manufacturer": "Elexa",
            "model": self._guardian.data[DATA_DIAGNOSTICS]["firmware"],
            "name": self._name,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name of the entity."""
        return f"Guardian {self._guardian.uid}: {self._name}"

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._guardian.uid}_{self._kind}"

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, TOPIC_UPDATE.format(self._guardian.uid), update
            )
        )

        await self._guardian.async_register_api_interest(self._kind)

        self.update_from_latest_data()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        self._guardian.async_deregister_api_interest(self._kind)

    @callback
    def update_from_latest_data(self):
        """Update the entity."""
        raise NotImplementedError
