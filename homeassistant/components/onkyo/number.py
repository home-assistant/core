"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    CONF_DEVICE_INFO,
    CONF_MAX_VOLUME,
    CONF_RECEIVER,
    DEFAULT_MAX_VOLUME,
    DOMAIN,
    MAX_VOLUME_MAX_VALUE,
    MAX_VOLUME_MIN_VALUE,
)
from .receiver import OnkyoNetworkReceiver, ReceiverZone

MAX_VOLUME_DESCRIPTION: NumberEntityDescription = NumberEntityDescription(
    key=CONF_MAX_VOLUME,
    name="Maximum Volume",
    icon="mdi:volume-high",
    entity_category=EntityCategory.CONFIG,
    native_min_value=MAX_VOLUME_MIN_VALUE,
    native_max_value=MAX_VOLUME_MAX_VALUE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up Number platform for passed config_entry."""
    device_info: DeviceInfo = hass.data[DOMAIN][config_entry.entry_id][CONF_DEVICE_INFO]
    receiver: OnkyoNetworkReceiver = hass.data[DOMAIN][config_entry.entry_id][
        CONF_RECEIVER
    ]

    new_devices: list[OnkyoNumberEntity] = []
    for zone in receiver.zones.values():
        if zone.supports_set_volume:
            new_devices.append(
                OnkyoRestoreNumberEntity(
                    zone, MAX_VOLUME_DESCRIPTION, device_info, DEFAULT_MAX_VOLUME
                )
            )

    # Add all new devices to HA.
    if new_devices:
        async_add_entities(new_devices)


class OnkyoNumberEntity(NumberEntity):
    """Representation of any Onkyo Number Entity."""

    _attr_should_poll: bool = False

    def __init__(
        self,
        receiver_zone: ReceiverZone,
        description: NumberEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the base number."""
        self.entity_description: NumberEntityDescription = description
        self._attr_unique_id: str = f"{receiver_zone.zone_identifier}_{description.key}"
        self._attr_device_info: DeviceInfo = device_info
        self._attr_name: str = f"{receiver_zone.name} {description.name}"
        self._receiver_zone: ReceiverZone = receiver_zone

    @property
    def native_value(self) -> int | None:
        """Return the value of the number entity."""
        return self._receiver_zone.get_config_value(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the entity."""
        self._receiver_zone.set_config_value(self.entity_description.key, int(value))
        self.async_write_ha_state()


class OnkyoRestoreNumberEntity(OnkyoNumberEntity, RestoreNumber):
    """Representation of an Onkyo Restore Number Entity."""

    def __init__(
        self,
        receiver_zone: ReceiverZone,
        description: NumberEntityDescription,
        device_info: DeviceInfo,
        default_value: int,
    ) -> None:
        """Initialize the restore number."""
        super().__init__(receiver_zone, description, device_info)
        self._default_value = default_value

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        if number_data := await self.async_get_last_number_data():
            # Get the last stored value and set the zone's config to it.
            self._receiver_zone.set_config_value(
                self.entity_description.key,
                int(number_data.native_value)
                if number_data.native_value is not None
                else self._default_value,
            )
