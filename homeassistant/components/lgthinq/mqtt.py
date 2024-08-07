"""Support for LG ThinQ Connect API."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.device_registry import (
    async_get as async_get_device_registry,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from thinqconnect.mqtt_client import ThinQMQTTClient

from .const import (
    DEVICE_ALIAS_CHANGED_MESSAGE,
    DEVICE_PUSH_MESSAGE,
    DEVICE_REGISTERED_MESSAGE,
    DEVICE_STATUS_MESSAGE,
    DEVICE_UNREGISTERED_MESSAGE,
    DOMAIN,
    MQTT_SUBSCRIPTION_INTERVAL,
    THINQ_DEVICE_ADDED,
    ThinqConfigEntry,
)
from .device import LGDevice, async_setup_lg_device
from .thinq import ThinQ

_LOGGER = logging.getLogger(__name__)


class ThinQMQTT:
    """A class for LG Connect-Client API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ThinqConfigEntry,
        thinq: ThinQ,
        client_id: str,
    ):
        self._hass = hass
        self._entry = entry
        self._thinq = thinq
        self._client_id = client_id
        self._mqtt_client: ThinQMQTTClient | None = None

    @property
    def mqtt_client(self) -> ThinQMQTTClient:
        """Returns the ThinQMQTTClient instance."""
        return self._mqtt_client

    async def async_refresh_subscribe(self, now: datetime | None = None) -> None:
        """Update event subscribes."""
        _LOGGER.debug("Attempting update event subscribes")
        device_entry_map: dict[str, LGDevice] = self._entry.runtime_data.lge_device_map

        if device_entry_map:
            tasks = [
                self._hass.async_create_task(
                    self._thinq.async_post_event_subscribe(
                        device_id=device.id,
                        body={"expire": {"unit": "HOUR", "timer": 24}},
                    )
                )
                for device in device_entry_map.values()
            ]

            await asyncio.gather(*tasks)

    async def async_start_subscribes(self) -> None:
        """Start push/event subscribes."""
        device_entry_map: dict[str, LGDevice] = self._entry.runtime_data.lge_device_map

        tasks = [
            self._hass.async_create_task(
                self._thinq.async_post_push_devices_subscribe()
            )
        ]

        if device_entry_map:
            tasks.extend(
                [
                    self._hass.async_create_task(
                        self._thinq.async_post_push_subscribe(device_id=device.id)
                    )
                    for device in device_entry_map.values()
                ]
            )

            tasks.extend(
                [
                    self._hass.async_create_task(
                        self._thinq.async_post_event_subscribe(
                            device_id=device.id,
                            body={"expire": {"unit": "HOUR", "timer": 24}},
                        )
                    )
                    for device in device_entry_map.values()
                ]
            )

        if tasks:
            await asyncio.gather(*tasks)

        await self._mqtt_client.async_connect_mqtt()

    async def async_end_subscribes(self, event: Event | None = None) -> None:
        """Start push/event unsubscribes."""
        device_entry_map: dict[str, LGDevice] = self._entry.runtime_data.lge_device_map

        tasks = [
            self._hass.async_create_task(
                self._thinq.async_delete_push_devices_subscribe()
            )
        ]

        if device_entry_map:
            tasks.extend(
                [
                    self._hass.async_create_task(
                        self._thinq.async_delete_push_subscribe(device_id=device.id)
                    )
                    for device in device_entry_map.values()
                ]
            )

            tasks.extend(
                [
                    self._hass.async_create_task(
                        self._thinq.async_delete_event_subscribe(device_id=device.id)
                    )
                    for device in device_entry_map.values()
                ]
            )

        if tasks:
            await asyncio.gather(*tasks)

    def on_connection_interrupted(
        self,
        connection,
        error,
        **kwargs: dict,
    ) -> None:
        """The MQTT connection is lost."""
        _LOGGER.error("Connection interrupted. error:=%s", error)

    def on_message_received(
        self,
        topic: str,
        payload: bytes,
        dup: bool,
        qos: Any,
        retain: bool,
        **kwargs: dict,
    ) -> None:
        """A message matching the topic is received."""
        try:
            received = json.loads(payload.decode())
        except ValueError:
            _LOGGER.error("Error parsing JSON payload: %s", payload.decode())
            return None

        _LOGGER.debug(
            "_on_message_received. topic : %s, received : %s",
            topic,
            received,
        )

        asyncio.run_coroutine_threadsafe(
            self.async_handle_device_event(message=received), self._hass.loop
        ).result()

    async def _async_update_device_status(
        self,
        message: dict,
        device: LGDevice,
        deleted_devices: list[str],
    ) -> None:
        push_type: str = message.get("pushType")
        if push_type == DEVICE_ALIAS_CHANGED_MESSAGE:
            device.handle_device_alias_changed(alias=message.get("alias"))
            return
        if push_type == DEVICE_UNREGISTERED_MESSAGE:
            device_registry: DeviceRegistry = async_get_device_registry(self._hass)
            device_entry: DeviceEntry = device_registry.async_get_device(
                identifiers={(DOMAIN, device.unique_id)}
            )
            if device_entry:
                device_registry.async_remove_device(device_entry.id)
                deleted_devices.append(device_entry.id)
            return

        if push_type == DEVICE_PUSH_MESSAGE:
            device.handle_notification_message(message=message.get("pushCode"))
        if push_type == DEVICE_STATUS_MESSAGE:
            device.update_partial_status(response=message.get("report"))

        # When new data arrives, use coordinator.async_set_updated_data(data)
        # to pass the data to the entities. If this method is used on a
        # coordinator that polls, it will reset the time until the next time
        # it will poll for data.
        device.coordinator.async_set_updated_data(None)

    async def async_handle_device_event(self, message: dict) -> None:
        """Handle received mqtt message."""
        device_id: str = message.get("deviceId")
        push_type: str = message.get("pushType")
        deleted_devices: list[str] = []

        if device_id is None or push_type is None:
            _LOGGER.error("No device specified. Invalid messsage.")
            return None

        if push_type == DEVICE_REGISTERED_MESSAGE:
            # Handle device add event
            # ToDo : await or create_task??
            # await self.async_add_device(message)
            self._hass.async_create_task(self._async_add_device(message))
            return None

        device_entry_map: dict[str, LGDevice] = self._entry.runtime_data.lge_device_map

        if not device_entry_map or device_entry_map is None:
            return None

        for device in device_entry_map.values():
            # Do not process events received from unregistered devices
            if device_id != device.id:
                continue
            # Update device status
            await self._async_update_device_status(message, device, deleted_devices)

        if deleted_devices:
            # Update lge_device_map
            for entry_id in deleted_devices:
                self._entry.runtime_data.lge_device_map.pop(entry_id)

    async def _async_add_device(self, message: dict) -> None:
        """Handle device register message."""
        device_id: str = message.get("deviceId")
        device_info: dict[str, Any] = {
            "deviceType": message.get("deviceType"),
            "modelName": message.get("modelName"),
            "alias": message.get("alias"),
            "reportable": message.get("reportable"),
        }

        # Setup devices.
        lg_device_list: list[LGDevice] = await async_setup_lg_device(
            self._hass,
            self._thinq,
            device={"deviceId": device_id, "deviceInfo": device_info},
        )

        if not lg_device_list or lg_device_list is None:
            _LOGGER.error(
                "There is no device list. skip setup. device_id=%s", device_id
            )
            return None

        # Register devices.
        device_entry_map: dict[str, LGDevice] = self._entry.runtime_data.lge_device_map
        device_registry: DeviceRegistry = async_get_device_registry(self._hass)
        for lg_device in lg_device_list:
            device_entry: DeviceEntry = device_registry.async_get_or_create(
                config_entry_id=self._entry.entry_id,
                **lg_device.device_info,
            )
            _LOGGER.debug(
                "Create device_registry. device_id=%s, device_entry_id=%s",
                lg_device.id,
                device_entry.id,
            )
            device_entry_map[device_entry.id] = lg_device

        async_dispatcher_send(self._hass, THINQ_DEVICE_ADDED, lg_device_list)

        # Request for a new subscription.
        self._hass.async_create_task(
            self._thinq.async_post_push_subscribe(device_id=device_id)
        )
        self._hass.async_create_task(
            self._thinq.async_post_event_subscribe(
                device_id=device_id,
                body={"expire": {"unit": "HOUR", "timer": 24}},
            )
        )

    async def async_connect_and_subscribe(self) -> None:
        """Initialize the connect-client component."""

        self._mqtt_client = await ThinQMQTTClient(
            thinq_api=self._thinq.api,
            client_id=self._client_id,
            on_message_received=self.on_message_received,
            on_connection_interrupted=self.on_connection_interrupted,
            on_connection_success=None,
            on_connection_failure=None,
            on_connection_closed=None,
        )

        if self._mqtt_client is None:
            # skip iniitalization if a valid MQTT client object cannot be obtained,
            return None

        # connect server and create certificate
        if not await self._mqtt_client.async_prepare_mqtt():
            # skip iniitalization if the client certificate is invalid
            return None

        # ready to subscribe
        self._hass.async_create_task(self.async_start_subscribes())
        self._entry.async_on_unload(
            async_track_time_interval(
                self._hass,
                self.async_refresh_subscribe,
                MQTT_SUBSCRIPTION_INTERVAL,
                cancel_on_shutdown=True,
            )
        )
        self._entry.async_on_unload(
            self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self.async_disconnect
            )
        )

    async def async_disconnect(self, event: Event | None = None) -> None:
        """Unregister client and disconnects handlers"""
        await self.async_end_subscribes()
        await self._mqtt_client.async_disconnect()
