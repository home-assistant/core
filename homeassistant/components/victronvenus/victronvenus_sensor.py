"""Support for Victron Venus sensors. The sensor itself has no logic, it simply receives messages and updates its state."""

from homeassistant.helpers.device_registry import DeviceInfo

from .const import PLACEHOLDER_PHASE
from .data_classes import ParsedTopic, TopicDescriptor
from .victronvenus_base import VictronVenusDeviceBase, VictronVenusSensorBase


class VictronVenusSensor(VictronVenusSensorBase):  # pylint: disable=hass-enforce-class-module
    """Representation of a Victron Venus sensor."""

    def __init__(
        self,
        device: VictronVenusDeviceBase,
        unique_id: str,
        descriptor: TopicDescriptor,
        parsed_topic: ParsedTopic,
        value: float | str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._descriptor = descriptor
        self._attr_native_unit_of_measurement = descriptor.unit_of_measurement
        self._attr_device_class = descriptor.device_class
        self._attr_state_class = descriptor.state_class
        self._attr_unique_id = unique_id
        self._attr_native_value = value
        self._attr_should_poll = False
        self._attr_has_entity_name = True
        self._attr_suggested_display_precision = descriptor.precision
        translation_key = descriptor.short_id
        translation_key = translation_key.replace(
            PLACEHOLDER_PHASE, "lx"
        )  # for translation key we do generic replacement
        self._attr_translation_key = translation_key
        if parsed_topic.phase is not None:
            self._attr_translation_placeholders = {"phase": parsed_topic.phase}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the sensor."""
        return self._device.device_info

    async def handle_message(self, parsed_topic, topic_desc, value):
        """Handle a message."""
        self._attr_native_value = value
        if self.registered_with_homeassistant:
            self.async_write_ha_state()
