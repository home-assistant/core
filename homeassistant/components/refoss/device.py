"""Entity for Refoss."""

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceInfo
from typing import Optional, List
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
)

from refoss_ha.controller.device import BaseDevice
from refoss_ha.util import calculate_id
from refoss_ha.enums import Namespace
from refoss_ha.const import DOMAIN, LOGGER
from .coordinator import RefossCoordinator


class RefossDevice(Entity):
    def __init__(
        self,
        device: BaseDevice,
        channel: int,
        coordinator: RefossCoordinator,
        platform: str,
        supplementary_classifiers: Optional[List[str]] = None,
    ) -> None:
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
            base_name += f" " + " ".join(supplementary_classifiers)
        else:
            self._id = calculate_id(
                platform=platform, uuid=device.uuid, channel=channel
            )

        self._entity_name = f"{base_name} - {channel}"

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def online(self) -> bool:
        return True

    @property
    def unique_id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._entity_name

    @property
    def device_info(self) -> DeviceInfo:
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
        try:
            await self.device.async_update()
        except Exception as e:
            LOGGER.warning(
                f"async_update:{self.device.uuid} {self.device.device_type}, e: {e}"
            )

    async def _async_push_notification_received(
        self, namespace: Namespace, data: dict, uuid: str
    ):
        full_update = True
        await self.device.async_update_push_state(
            namespace=namespace, data=data, uuid=uuid
        )
        self.async_schedule_update_ha_state(force_refresh=full_update)

    async def async_added_to_hass(self) -> None:
        self.device.register_push_notification_handler_coroutine(
            self._async_push_notification_received
        )
        self.hass.data[DOMAIN]["ADDED_ENTITIES_IDS"].add(self.unique_id)

    async def async_will_remove_from_hass(self) -> None:
        self.device.unregister_push_notification_handler_coroutine(
            self._async_push_notification_received
        )
        self.hass.data[DOMAIN]["ADDED_ENTITIES_IDS"].remove(self.unique_id)
