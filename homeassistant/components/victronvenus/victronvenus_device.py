"""Logic for handling Victron devices, and routing updates to the appropriate sensors."""

from logging import getLogger

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DEVICE_MESSAGE, DOMAIN, PLACEHOLDER_PHASE, SENSOR_MESSAGE
from .data_classes import ParsedTopic, TopicDescriptor
from .victronvenus_base import (
    VictronVenusDeviceBase,
    VictronVenusHubBase,
    VictronVenusSensorBase,
)
from .victronvenus_sensor import VictronVenusSensor

_LOGGER = getLogger(__name__)


class VictronDevice(VictronVenusDeviceBase):
    """Class to represent a Victron device."""

    def __init__(
        self,
        hub: VictronVenusHubBase,
        unqiue_id: str,
        descriptor: TopicDescriptor,
        installation_id: str,
        device_type: str,
        device_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(hub)
        self._descriptor = descriptor
        self.unique_id = unqiue_id
        self._sensors: dict[str, VictronVenusSensor] = {}
        self._root_device_name: str | None = None

        self._device_info = DeviceInfo(identifiers={(DOMAIN, self.unique_id)})

        if device_type != "system":
            self._device_info["via_device"] = (DOMAIN, f"{installation_id}_system_0")

    def _set_device_property_from_topic(
        self, parsed_topic: ParsedTopic, topic_desc: TopicDescriptor, payload: str
    ) -> None:
        """Set a device property from a topic."""
        short_id = topic_desc.short_id
        if topic_desc.unwrapper is not None:
            payload = str(topic_desc.unwrapper(payload))

        if short_id == "victron_productid":
            return  # ignore for now

        match short_id:
            case "model":
                self._device_info["model"] = payload
            case "serial_number":
                self._device_info["serial_number"] = payload
            case "manufacturer":
                self._device_info["manufacturer"] = payload
            case _:
                _LOGGER.warning(
                    "Unhandled device property %s for %s", short_id, self.unique_id
                )

        # if we get a model message and we don't have a name yet, we use the model as name

        if short_id == "model" and "name" not in self._device_info:
            self._device_info["name"] = payload

    async def handle_message(
        self, parsed_topic: ParsedTopic, topic_desc: TopicDescriptor, payload: str
    ) -> None:
        """Handle a message."""

        if topic_desc.message_type == DEVICE_MESSAGE:
            self._set_device_property_from_topic(parsed_topic, topic_desc, payload)

        elif topic_desc.message_type == SENSOR_MESSAGE:
            value: str | int | float | None = payload
            if topic_desc.unwrapper is not None:
                value = topic_desc.unwrapper(payload)
            if value is None:
                return  # don't try to create or update sensor if we don't have valid values for it.

            short_id = topic_desc.short_id
            if PLACEHOLDER_PHASE in short_id:
                short_id = short_id.replace(PLACEHOLDER_PHASE, parsed_topic.phase)
            sensor_id = f"{self.unique_id}_{short_id}"

            sensor = self._get_or_create_sensor(
                sensor_id, parsed_topic, topic_desc, payload
            )

            await sensor.handle_message(parsed_topic, topic_desc, value)

    def _get_or_create_sensor(
        self,
        sensor_id: str,
        parsed_topic: ParsedTopic,
        topic_desc: TopicDescriptor,
        payload: str,
    ) -> "VictronVenusSensor":
        sensor = self._sensors.get(sensor_id)
        if sensor is None:
            sensor = VictronVenusSensor(
                self, sensor_id, topic_desc, parsed_topic, payload
            )
            self._sensors[sensor_id] = sensor

        return sensor

    def set_root_device_name(self, name: str) -> None:
        """Set the name of the root device."""
        self._root_device_name = name
        self._device_info["name"] = name

    @property
    def victron_sensors(self) -> list[VictronVenusSensorBase]:
        """Returns the list of sensors on this device."""
        return list(self._sensors.values())

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the device. Note the information will be incomplete until the first full refresh."""
        return self._device_info
