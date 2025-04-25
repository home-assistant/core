"""Sensor platform for Hyperion."""

from __future__ import annotations

import functools
from typing import Any

from hyperion import client
from hyperion.const import (
    KEY_COMPONENTID,
    KEY_ORIGIN,
    KEY_OWNER,
    KEY_PRIORITIES,
    KEY_PRIORITY,
    KEY_RGB,
    KEY_UPDATE,
    KEY_VALUE,
    KEY_VISIBLE,
)

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import (
    HyperionConfigEntry,
    get_hyperion_device_id,
    get_hyperion_unique_id,
    listen_for_instance_updates,
)
from .const import (
    DOMAIN,
    HYPERION_MANUFACTURER_NAME,
    HYPERION_MODEL_NAME,
    SIGNAL_ENTITY_REMOVE,
    TYPE_HYPERION_SENSOR_BASE,
    TYPE_HYPERION_SENSOR_VISIBLE_PRIORITY,
)

SENSORS = [TYPE_HYPERION_SENSOR_VISIBLE_PRIORITY]
PRIORITY_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="visible_priority",
    translation_key="visible_priority",
    icon="mdi:lava-lamp",
)


def _sensor_unique_id(server_id: str, instance_num: int, suffix: str) -> str:
    """Calculate a sensor's unique_id."""
    return get_hyperion_unique_id(
        server_id,
        instance_num,
        f"{TYPE_HYPERION_SENSOR_BASE}_{suffix}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Hyperion platform from config entry."""
    server_id = entry.unique_id

    @callback
    def instance_add(instance_num: int, instance_name: str) -> None:
        """Add entities for a new Hyperion instance."""
        assert server_id
        sensors = [
            HyperionVisiblePrioritySensor(
                server_id,
                instance_num,
                instance_name,
                entry.runtime_data.instance_clients[instance_num],
                PRIORITY_SENSOR_DESCRIPTION,
            )
        ]

        async_add_entities(sensors)

    @callback
    def instance_remove(instance_num: int) -> None:
        """Remove entities for an old Hyperion instance."""
        assert server_id

        for sensor in SENSORS:
            async_dispatcher_send(
                hass,
                SIGNAL_ENTITY_REMOVE.format(
                    _sensor_unique_id(server_id, instance_num, sensor),
                ),
            )

    listen_for_instance_updates(hass, entry, instance_add, instance_remove)


class HyperionSensor(SensorEntity):
    """Sensor class."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        server_id: str,
        instance_num: int,
        instance_name: str,
        hyperion_client: client.HyperionClient,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = entity_description
        self._client = hyperion_client
        self._attr_native_value = None
        self._client_callbacks: dict[str, Any] = {}

        device_id = get_hyperion_device_id(server_id, instance_num)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=HYPERION_MANUFACTURER_NAME,
            model=HYPERION_MODEL_NAME,
            name=instance_name,
            configuration_url=self._client.remote_url,
        )

    @property
    def available(self) -> bool:
        """Return server availability."""
        return bool(self._client.has_loaded_state)

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ENTITY_REMOVE.format(self._attr_unique_id),
                functools.partial(self.async_remove, force_remove=True),
            )
        )

        self._client.add_callbacks(self._client_callbacks)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup prior to hass removal."""
        self._client.remove_callbacks(self._client_callbacks)


class HyperionVisiblePrioritySensor(HyperionSensor):
    """Class that displays the visible priority of a Hyperion instance."""

    def __init__(
        self,
        server_id: str,
        instance_num: int,
        instance_name: str,
        hyperion_client: client.HyperionClient,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(
            server_id, instance_num, instance_name, hyperion_client, entity_description
        )

        self._attr_unique_id = _sensor_unique_id(
            server_id, instance_num, TYPE_HYPERION_SENSOR_VISIBLE_PRIORITY
        )

        self._client_callbacks = {
            f"{KEY_PRIORITIES}-{KEY_UPDATE}": self._update_priorities
        }

    @callback
    def _update_priorities(self, _: dict[str, Any] | None = None) -> None:
        """Update Hyperion priorities."""
        state_value = None
        attrs = {}

        for priority in self._client.priorities or []:
            if not (KEY_VISIBLE in priority and priority[KEY_VISIBLE] is True):
                continue

            if priority[KEY_COMPONENTID] == "COLOR":
                state_value = priority[KEY_VALUE][KEY_RGB]
            else:
                state_value = priority.get(KEY_OWNER)

            attrs = {
                "component_id": priority[KEY_COMPONENTID],
                "origin": priority[KEY_ORIGIN],
                "priority": priority[KEY_PRIORITY],
                "owner": priority.get(KEY_OWNER),
            }

            if priority[KEY_COMPONENTID] == "COLOR":
                attrs["color"] = priority[KEY_VALUE]
            else:
                attrs["color"] = None

        self._attr_native_value = state_value
        self._attr_extra_state_attributes = attrs

        self.async_write_ha_state()
