"""Support for select entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, override

from aioamazondevices.structures import AmazonDropInStatus

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import AmazonConfigEntry, AmazonDevice, alexa_api_call
from .entity import AmazonEntity, AmazonServiceEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AmazonSelectEntityDescription(SelectEntityDescription):
    """Alexa Devices select entity description."""

    method: str
    is_available_fn: Callable[[AmazonDevice], bool] = lambda device: True


SELECTS: Final = (
    AmazonSelectEntityDescription(
        key="dropin",
        translation_key="dropin",
        entity_category=EntityCategory.CONFIG,
        method="set_dropin_status",
        # API values: "All", "Home", "Off"
        options=[status.value.lower() for status in AmazonDropInStatus],
        is_available_fn=lambda device: (
            device.communication_settings.get("dropin") is not None
        ),
    ),
)

SERVICE_SELECTS: Final = (
    AmazonSelectEntityDescription(
        key="default_device",
        translation_key="default_device",
        entity_category=EntityCategory.CONFIG,
        method="set_default_device",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities based on a config entry."""
    coordinator = entry.runtime_data

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            select_entities = [
                AmazonSelectEntity(coordinator, serial_num, select_desc)
                for select_desc in SELECTS
                for serial_num in new_devices
                if select_desc.is_available_fn(coordinator.data[serial_num])
            ]
            select_service_entites = [
                AmazonSelectServiceEntity(coordinator, select_desc)
                for select_desc in SERVICE_SELECTS
                for serial_num in new_devices
                if select_desc.is_available_fn(coordinator.data[serial_num])
            ]
            async_add_entities(select_entities)
            async_add_entities(select_service_entites)

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class AmazonSelectEntity(AmazonEntity, SelectEntity):
    """Representation of a select entity."""

    entity_description: AmazonSelectEntityDescription

    @property
    @override
    def options(self) -> list[str]:
        """Return a list of available options."""
        if TYPE_CHECKING:
            assert self.entity_description.options is not None

        return self.entity_description.options

    @property
    def _device(self) -> AmazonDevice:
        """Return the device."""
        return self.coordinator.data[self._serial_num]

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last known option."""
        await super().async_added_to_hass()
        self._attr_current_option = self._device.communication_settings[
            self.entity_description.key
        ].lower()

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        method = getattr(self.coordinator.api, self.entity_description.method)

        if TYPE_CHECKING:
            assert method is not None

        async with alexa_api_call(self.coordinator):
            await method(self.device, AmazonDropInStatus(option.capitalize()))

        self._attr_current_option = option
        self.async_write_ha_state()


class AmazonSelectServiceEntity(AmazonServiceEntity, SelectEntity, RestoreEntity):
    """Representation of a service select entity."""

    entity_description: AmazonSelectEntityDescription

    @property
    @override
    def options(self) -> list[str]:
        """Return a list of available options."""
        return [device.account_name for device in self.coordinator.data.values()]

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last known option."""
        await super().async_added_to_hass()
        if (default := self.coordinator.api.default_device) is not None:
            self._attr_current_option = default.account_name
        if (
            last_state := await self.async_get_last_state()
        ) and last_state.state in self.options:
            await self.async_select_option(last_state.state)

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for device in self.coordinator.data.values():
            if device.account_name == option:
                self.coordinator.api.default_device = device
                self._attr_current_option = option
                self.async_write_ha_state()
                return
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="select_option_not_found",
            translation_placeholders={"option": option},
        )
