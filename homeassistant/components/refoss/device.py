"""Entity for Refoss."""

from __future__ import annotations

from typing import Optional

from refoss_ha.const import DOMAIN
from refoss_ha.controller.device import BaseDevice
from refoss_ha.enums import Namespace
from refoss_ha.util import calculate_id

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from .coordinator import RefossCoordinator


class RefossDevice(Entity):
    """RefossDevice."""

    def __init__(
        self,
        device: BaseDevice,
        channel: int,
        coordinator: RefossCoordinator,
        platform: str,
        supplementary_classifiers: Optional[list[str]] = None,
    ) -> None:
        """__init__."""
        self.device = device
        self._model = device.device_type
        self._api_url = device.inner_ip
        self._device_id = device.uuid
        self._channel_id = channel

        self._coordinator = coordinator
        self._last_http_state = None
        base_name = f"{device.dev_name} ({device.device_type})"
        if supplementary_classifiers is not None:
            self._id = calculate_id(
                platform=platform,
                uuid=device.uuid,
                channel=channel,
                supplementary_classifiers=supplementary_classifiers,
            )
            base_name += " " + " ".join(supplementary_classifiers)
        else:
            self._id = calculate_id(
                platform=platform, uuid=device.uuid, channel=channel
            )

        self._entity_name = f"{base_name} - {channel}"

    @property
    def should_poll(self) -> bool:
        """should_poll."""
        return True

    @property
    def online(self) -> bool:
        """online."""
        return True

    @property
    def unique_id(self) -> str:
        """unique_id."""
        return self._id

    @property
    def name(self) -> str:
        """name."""
        return self._entity_name

    @property
    def device_info(self) -> DeviceInfo:
        """device_info."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="refoss",
            model=self._model,
            name=self.device.dev_name,
            connections={(CONNECTION_NETWORK_MAC, self._device_id)},
            sw_version=self.device.fmware_version,
            hw_version=self.device.hdware_version,
        )

        return device_info

    async def async_update(self):
        """async_update."""
        await self.device.async_update()

    async def _async_push_notification_received(
        self, namespace: Namespace, data: dict, uuid: str
    ):
        """_async_push_notification_received."""
        full_update = True
        await self.device.async_update_push_state(
            namespace=namespace, data=data, uuid=uuid
        )
        self.async_schedule_update_ha_state(force_refresh=full_update)

    async def async_added_to_hass(self) -> None:
        """async_added_to_hass."""
        self.device.register_push_notification_handler_coroutine(
            self._async_push_notification_received
        )
        self.hass.data[DOMAIN]["ADDED_ENTITIES_IDS"].add(self.unique_id)

    async def async_will_remove_from_hass(self) -> None:
        """async_will_remove_from_hass."""
        self.device.unregister_push_notification_handler_coroutine(
            self._async_push_notification_received
        )
        self.hass.data[DOMAIN]["ADDED_ENTITIES_IDS"].remove(self.unique_id)
