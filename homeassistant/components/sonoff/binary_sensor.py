import asyncio

from homeassistant.components.binary_sensor import BinarySensorEntity, \
    BinarySensorDeviceClass
from homeassistant.components.script import ATTR_LAST_TRIGGERED
from homeassistant.const import STATE_ON
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt

from .core.const import DOMAIN
from .core.entity import XEntity
from .core.ewelink import XRegistry, SIGNAL_ADD_ENTITIES

PARALLEL_UPDATES = 0  # fix entity_platform parallel_updates Semaphore


async def async_setup_entry(hass, config_entry, add_entities):
    ewelink: XRegistry = hass.data[DOMAIN][config_entry.entry_id]
    ewelink.dispatcher_connect(
        SIGNAL_ADD_ENTITIES, lambda x: add_entities(
            [e for e in x if isinstance(e, BinarySensorEntity)]
        )
    )


# noinspection PyUnresolvedReferences
DEVICE_CLASSES = {cls.value: cls for cls in BinarySensorDeviceClass}


# noinspection PyAbstractClass
class XBinarySensor(XEntity, BinarySensorEntity):
    def __init__(self, ewelink: XRegistry, device: dict):
        XEntity.__init__(self, ewelink, device)
        device_class = device.get("device_class")
        if device_class in DEVICE_CLASSES:
            self._attr_device_class = DEVICE_CLASSES[device_class]


# noinspection PyAbstractClass
class XWiFiDoor(XBinarySensor):
    params = {"switch"}
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def set_state(self, params: dict):
        self._attr_is_on = params['switch'] == 'on'

    def internal_available(self) -> bool:
        # device with buggy online status
        return self.ewelink.cloud.online


# noinspection PyAbstractClass
class XZigbeeMotion(XBinarySensor):
    params = {"motion", "online"}

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def set_state(self, params: dict):
        if "motion" in params:
            self._attr_is_on = params['motion'] == 1
        elif params.get("online") is False:
            # Fix stuck in `on` state after bridge goes to unavailable
            # https://github.com/AlexxIT/SonoffLAN/pull/425
            self._attr_is_on = False


# noinspection PyAbstractClass
class XZigbeeDoor(XBinarySensor):
    params = {"lock"}

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def set_state(self, params: dict):
        self._attr_is_on = params['lock'] == 1


class XWater(XBinarySensor):
    params = {"water"}

    def set_state(self, params: dict):
        self._attr_is_on = params['water'] == 1


# noinspection PyAbstractClass
class XRemoteSensor(BinarySensorEntity, RestoreEntity):
    _attr_is_on = False
    task: asyncio.Task = None

    def __init__(self, ewelink: XRegistry, bridge: dict, child: dict):
        self.ewelink = ewelink
        self.channel = child["channel"]
        self.timeout = child.get("timeout", 120)

        self._attr_device_class = DEVICE_CLASSES.get(child.get("device_class"))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bridge['deviceid'])}
        )
        self._attr_extra_state_attributes = {}
        self._attr_name = child["name"]
        self._attr_unique_id = f"{bridge['deviceid']}_{self.channel}"

        self.entity_id = DOMAIN + "." + self._attr_unique_id

    def internal_update(self, ts: str):
        if self.task:
            self.task.cancel()

        self._attr_extra_state_attributes = {ATTR_LAST_TRIGGERED: ts}
        self._attr_is_on = True
        self._async_write_ha_state()

        if self.timeout:
            self.task = asyncio.create_task(self.clear_state(self.timeout))

    async def clear_state(self, delay: int):
        await asyncio.sleep(delay)
        self._attr_is_on = False
        self._async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        # restore previous sensor state
        # if sensor has timeout - restore remaining timer and check expired
        restore = await self.async_get_last_state()
        if not restore:
            return

        self._attr_is_on = restore.state == STATE_ON

        if self.is_on and self.timeout:
            ts = restore.attributes[ATTR_LAST_TRIGGERED]
            left = self.timeout - (dt.utcnow() - dt.parse_datetime(ts)).seconds
            if left > 0:
                self.task = asyncio.create_task(self.clear_state(left))
            else:
                self._attr_is_on = False

    async def async_will_remove_from_hass(self):
        if self.task:
            self.task.cancel()


class XRemoteSensorOff:
    def __init__(self, child: dict, sensor: XRemoteSensor):
        self.channel = child["channel"]
        self.name = child["name"]
        self.sensor = sensor

    # noinspection PyProtectedMember
    def internal_update(self, ts: str):
        self.sensor._attr_is_on = False
        self.sensor._async_write_ha_state()
