"""Platform for binarysensor integration."""
import logging

from boschshcpy import SHCSession, SHCShutterContact, SHCSmokeDetector

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_WINDOW,
    BinarySensorDevice,
)
from homeassistant.const import CONF_IP_ADDRESS

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the SHC binary sensor platform."""
    device = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id]

    for binarysensor in session.device_helper.shutter_contacts:
        _LOGGER.debug(
            "Found shutter contact: %s (%s)", binarysensor.name, binarysensor.id
        )
        device.append(
            ShutterContactSensor(
                device=binarysensor,
                room_name=session.room(binarysensor.room_id).name,
                controller_ip=config_entry.data[CONF_IP_ADDRESS],
            )
        )

    for binarysensor in session.device_helper.smoke_detectors:
        _LOGGER.debug(
            "Found smoke detector: %s (%s)", binarysensor.name, binarysensor.id
        )
        device.append(
            SmokeDetectorSensor(
                device=binarysensor,
                room_name=session.room(binarysensor.room_id).name,
                controller_ip=config_entry.data[CONF_IP_ADDRESS],
            )
        )

    if device:
        async_add_entities(device)


class ShutterContactSensor(BinarySensorDevice):
    """Representation of a SHC shutter contact sensor."""

    def __init__(self, device: SHCShutterContact, room_name: str, controller_ip: str):
        """Initialize the SHC device."""
        self._device = device
        self._room_name = room_name
        self._controller_ip = controller_ip

    async def async_added_to_hass(self):
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed():
            self.schedule_update_ha_state()

        for service in self._device.device_services:
            service.subscribe_callback(self.entity_id, on_state_changed)

    async def async_will_remove_from_hass(self):
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        for service in self._device.device_services:
            service.unsubscribe_callback(self.entity_id)

    @property
    def unique_id(self):
        """Return the unique ID of this binary sensor."""
        return self._device.serial

    @property
    def device_id(self):
        """Return the ID of this binary sensor."""
        return self._device.id

    @property
    def root_device(self):
        """Return the root device id."""
        return self._device.root_device_id

    @property
    def name(self):
        """Name of the device."""
        return self._device.name

    @property
    def manufacturer(self):
        """Manufacturer of the device."""
        return self._device.manufacturer

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self._device.device_model,
            "sw_version": "",
            "via_device": (DOMAIN, self._controller_ip),
        }

    @property
    def should_poll(self):
        """Set polling mode."""
        return False

    @property
    def available(self):
        """Return false if status is unavailable."""
        if self._device.status == "AVAILABLE":
            return True
        return False

    @property
    def is_on(self):
        """Return the state of the sensor."""
        if self._device.state == SHCShutterContact.ShutterContactService.State.OPEN:
            return True
        if self._device.state == SHCShutterContact.ShutterContactService.State.CLOSED:
            return False
        return None

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        switcher = {
            SHCShutterContact.DeviceClass.ENTRANCE_DOOR: DEVICE_CLASS_DOOR,
            SHCShutterContact.DeviceClass.REGULAR_WINDOW: DEVICE_CLASS_WINDOW,
            SHCShutterContact.DeviceClass.FRENCH_WINDOW: DEVICE_CLASS_DOOR,
            SHCShutterContact.DeviceClass.GENERIC: DEVICE_CLASS_WINDOW,
        }
        return switcher.get(self._device.device_class, DEVICE_CLASS_WINDOW)

    def update(self):
        """Trigger an update of the device."""
        self._device.update()

    @property
    def state_attributes(self):
        """Extend state attribute of the device."""
        state_attr = super().state_attributes
        if state_attr is None:
            state_attr = dict()
        state_attr["boschshc_room_name"] = self._room_name
        return state_attr


class SmokeDetectorSensor(BinarySensorDevice):
    """Representation of a SHC smoke detector sensor."""

    def __init__(self, device: SHCSmokeDetector, room_name: str, controller_ip: str):
        """Initialize the SHC device."""
        self._device = device
        self._room_name = room_name
        self._controller_ip = controller_ip

    async def async_added_to_hass(self):
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed():
            self.schedule_update_ha_state()

        for service in self._device.device_services:
            service.subscribe_callback(self.entity_id, on_state_changed)

    async def async_will_remove_from_hass(self):
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        for service in self._device.device_services:
            service.unsubscribe_callback(self.entity_id)

    @property
    def unique_id(self):
        """Return the unique ID of this binary sensor."""
        return self._device.serial

    @property
    def device_id(self):
        """Return the ID of this binary sensor."""
        return self._device.id

    @property
    def root_device(self):
        """Return the root device id."""
        return self._device.root_device_id

    @property
    def name(self):
        """Name of the device."""
        return self._device.name

    @property
    def manufacturer(self):
        """Manufacturer of the device."""
        return self._device.manufacturer

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self._device.device_model,
            "sw_version": "",
            "via_device": (DOMAIN, self._controller_ip),
        }

    @property
    def should_poll(self):
        """Report polling mode."""
        return False

    @property
    def available(self):
        """Return false if status is unavailable."""
        if self._device.status == "AVAILABLE":
            return True

        return False

    @property
    def is_on(self):
        """Return the state of the sensor."""
        if self._device.alarmstate == SHCSmokeDetector.AlarmService.State.IDLE_OFF:
            return False

        return True

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SMOKE

    def update(self):
        """Trigger an update of the device."""
        self._device.update()

    @property
    def state_attributes(self):
        """Extend state attribute of the device."""
        state_attr = super().state_attributes
        if state_attr is None:
            state_attr = dict()
        state_attr["boschshc_room_name"] = self._room_name
        state_attr["boschshc_smokedetector_checkstate"] = (
            "OK"
            if self._device.smokedetectorcheck_state
            == SHCSmokeDetector.SmokeDetectorCheckService.State.SMOKE_TEST_OK
            else None
        )
        return state_attr
