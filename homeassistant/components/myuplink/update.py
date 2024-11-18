"""Update entity for myUplink."""

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyUplinkConfigEntry, MyUplinkDataCoordinator
from .entity import MyUplinkEntity

UPDATE_DESCRIPTION = UpdateEntityDescription(
    key="update",
    device_class=UpdateDeviceClass.FIRMWARE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyUplinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entity."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MyUplinkDeviceUpdate(
            coordinator=coordinator,
            device_id=device_id,
            entity_description=UPDATE_DESCRIPTION,
            unique_id_suffix="upd",
        )
        for device_id in coordinator.data.devices
    )


class MyUplinkDeviceUpdate(MyUplinkEntity, UpdateEntity):
    """Representation of a myUplink device update entity."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        entity_description: UpdateEntityDescription,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        self.entity_description = entity_description

    @property
    def installed_version(self) -> str | None:
        """Return installed_version."""
        return self.coordinator.data.devices[self.device_id].firmwareCurrent

    @property
    def latest_version(self) -> str | None:
        """Return latest_version."""
        return self.coordinator.data.devices[self.device_id].firmwareDesired
