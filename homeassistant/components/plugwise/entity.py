"""Generic Plugwise Entity Class."""
from __future__ import annotations

from plugwise.smile import Smile

from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    ATTR_MODEL,
    ATTR_VIA_DEVICE,
    CONF_HOST,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class PlugwiseEntity(CoordinatorEntity):
    """Represent a PlugWise Entity."""

    def __init__(
        self, api: Smile, coordinator: DataUpdateCoordinator, name: str, dev_id: str
    ) -> None:
        """Initialise the gateway."""
        super().__init__(coordinator)

        self._api = api
        self._name = name
        self._dev_id = dev_id

        self._unique_id: str | None = None
        self._model: str | None = None

        self._entity_name = self._name

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str | None:
        """Return the name of the entity, if any."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        device_information = DeviceInfo(
            identifiers={(DOMAIN, self._dev_id)},
            name=self._entity_name,
            manufacturer="Plugwise",
        )

        if entry := self.coordinator.config_entry:
            device_information[
                ATTR_CONFIGURATION_URL
            ] = f"http://{entry.data[CONF_HOST]}"

        if self._model is not None:
            device_information[ATTR_MODEL] = self._model.replace("_", " ").title()

        if self._dev_id != self._api.gateway_id:
            device_information[ATTR_VIA_DEVICE] = (DOMAIN, str(self._api.gateway_id))

        return device_information

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._async_process_data()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_process_data)
        )

    @callback
    def _async_process_data(self) -> None:
        """Interpret and process API data."""
        raise NotImplementedError
