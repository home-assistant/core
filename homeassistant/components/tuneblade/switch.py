import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    added_device_ids = set()
    entities = []

    devices = coordinator.data or {}

    # Add special master (hub) switch if present
    if "MASTER" in devices:
        entities.append(TuneBladeHubSwitch(coordinator))
        added_device_ids.add("MASTER")

    # Add switches for all other devices
    for device_id, device_data in devices.items():
        if device_id not in added_device_ids:
            entities.append(TuneBladeDeviceSwitch(coordinator, device_id, device_data))
            added_device_ids.add(device_id)
            _LOGGER.debug("Added TuneBlade device switch: %s", device_data.get("name", device_id))

    async_add_entities(entities)

    # Dynamically add new devices after setup
    def _update_entities():
        new_entities = []
        for device_id, device_data in (coordinator.data or {}).items():
            if device_id not in added_device_ids:
                new_entities.append(TuneBladeDeviceSwitch(coordinator, device_id, device_data))
                added_device_ids.add(device_id)
                _LOGGER.debug("Dynamically added TuneBlade device switch: %s", device_data.get("name", device_id))
        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(_update_entities)


class TuneBladeDeviceSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to connect/disconnect individual TuneBlade devices."""

    def __init__(self, coordinator, device_id, device_data):
        super().__init__(coordinator)
        self._device_id = device_id
        self._name = device_data.get("name", device_id)

    @property
    def unique_id(self):
        safe_name = self._name.replace(" ", "_")
        return f"{self._device_id}@{safe_name}_switch"

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        device = self.coordinator.data.get(self._device_id)
        if not device:
            return False
        return device.get("connected", False)

    async def async_turn_on(self):
        _LOGGER.debug("Connecting TuneBlade device: %s", self._name)
        await self.coordinator.client.connect(self._device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        _LOGGER.debug("Disconnecting TuneBlade device: %s", self._name)
        await self.coordinator.client.disconnect(self._device_id)
        await self.coordinator.async_request_refresh()

    @property
    def available(self):
        return self._device_id in self.coordinator.data

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "via_device": (DOMAIN, "MASTER"),  # Link to hub device
            "name": self._name,
            "manufacturer": "TuneBlade",
        }

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self._handle_coordinator_update)
        self._handle_coordinator_update()

    def _handle_coordinator_update(self):
        self.async_write_ha_state()


class TuneBladeHubSwitch(CoordinatorEntity, SwitchEntity):
    """Special switch for the TuneBlade hub master device."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Master"
        self._attr_unique_id = "tuneblade_master_switch"

    @property
    def is_on(self):
        master_data = self.coordinator.data.get("MASTER")
        if not master_data:
            return False
        return master_data.get("connected", False)

    async def async_turn_on(self):
        _LOGGER.debug("Connecting TuneBlade Hub master")
        await self.coordinator.client.connect("MASTER")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        _LOGGER.debug("Disconnecting TuneBlade Hub master")
        await self.coordinator.client.disconnect("MASTER")
        await self.coordinator.async_request_refresh()

    @property
    def available(self):
        return "MASTER" in self.coordinator.data

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "MASTER")},
            "name": self._attr_name,
            "manufacturer": "TuneBlade",
            "entry_type": "service",
        }

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self._handle_coordinator_update)
        self._handle_coordinator_update()

    def _handle_coordinator_update(self):
        self.async_write_ha_state()
