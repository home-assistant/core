"""LCN parent entity class."""

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_DOMAIN, CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DOMAIN_DATA, DOMAIN
from .helpers import (
    AddressType,
    DeviceConnectionType,
    InputType,
    generate_unique_id,
    get_device_connection,
    get_resource,
)


class LcnEntity(Entity):
    """Parent class for all entities associated with the LCN component."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    device_connection: DeviceConnectionType

    def __init__(
        self,
        config: ConfigType,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the LCN device."""
        self.config = config
        self.config_entry = config_entry
        self.address: AddressType = config[CONF_ADDRESS]
        self._unregister_for_inputs: Callable | None = None
        self._name: str = config[CONF_NAME]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    generate_unique_id(self.config_entry.entry_id, self.address),
                )
            },
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return generate_unique_id(
            self.config_entry.entry_id,
            self.address,
            get_resource(
                self.config[CONF_DOMAIN], self.config[CONF_DOMAIN_DATA]
            ).lower(),
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.device_connection = get_device_connection(
            self.hass, self.config[CONF_ADDRESS], self.config_entry
        )
        if not self.device_connection.is_group:
            self._unregister_for_inputs = self.device_connection.register_for_inputs(
                self.input_received
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._unregister_for_inputs is not None:
            self._unregister_for_inputs()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    def input_received(self, input_obj: InputType) -> None:
        """Set state/value when LCN input object (command) is received."""
