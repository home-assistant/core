"""Support for YoLink Device."""

from __future__ import annotations

from abc import abstractmethod

from yolink.client_request import ClientRequest
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import YoLinkCoordinator


class YoLinkEntity(CoordinatorEntity[YoLinkCoordinator]):
    """YoLink Device Basic Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
    ) -> None:
        """Init YoLink Entity."""
        super().__init__(coordinator)
        self.config_entry = config_entry

    @property
    def device_id(self) -> str:
        """Return the device id of the YoLink device."""
        return self.coordinator.device.device_id

    async def async_added_to_hass(self) -> None:
        """Update state."""
        await super().async_added_to_hass()
        return self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state."""
        data = self.coordinator.data
        if data is not None:
            self.update_entity_state(data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for HA."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device.device_id)},
            manufacturer=MANUFACTURER,
            model=self.coordinator.device.device_type,
            model_id=self.coordinator.device.device_model_name,
            name=self.coordinator.device.device_name,
        )

    @callback
    @abstractmethod
    def update_entity_state(self, state: dict) -> None:
        """Parse and update entity state, should be overridden."""

    async def call_device(self, request: ClientRequest) -> None:
        """Call device api."""
        try:
            # call_device will check result, fail by raise YoLinkClientError
            await self.coordinator.device.call_device(request)
        except YoLinkAuthFailError as yl_auth_err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(yl_auth_err) from yl_auth_err
        except YoLinkClientError as yl_client_err:
            raise HomeAssistantError(yl_client_err) from yl_client_err
