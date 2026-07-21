"""Button platform for Enphase Envoy solar energy monitor."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from pyenphase import Envoy
from pyenphase.const import SupportedFeatures

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity, exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class EnvoyACBButtonEntityDescription(ButtonEntityDescription):
    """Describes an Envoy ACB battery button entity."""

    press_fn: Callable[
        [Envoy, list[str], int, int], Coroutine[Any, Any, dict[str, Any]]
    ]


ACB_BUTTONS = (
    EnvoyACBButtonEntityDescription(
        key="acb_sleep",
        translation_key="acb_sleep",
        press_fn=lambda envoy, serials, low, high: envoy.set_acb_sleep(
            [
                {"serial_num": serial, "sleep_min_soc": low, "sleep_max_soc": high}
                for serial in serials
            ]
        ),
    ),
    EnvoyACBButtonEntityDescription(
        key="acb_wake",
        translation_key="acb_wake",
        press_fn=lambda envoy, serials, low, high: envoy.clear_acb_sleep(serials),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnphaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up envoy button platform."""
    coordinator = config_entry.runtime_data
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    if not (
        envoy_data.acb_inventory
        and coordinator.envoy.supported_features & SupportedFeatures.ACB
    ):
        return

    entities: list[ButtonEntity] = [
        EnvoyACBButtonEntity(coordinator, description) for description in ACB_BUTTONS
    ]
    async_add_entities(entities)


class EnvoyACBButtonEntity(EnvoyBaseEntity, ButtonEntity):
    """Envoy button that puts all ACB batteries to sleep or wakes them."""

    entity_description: EnvoyACBButtonEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyACBButtonEntityDescription,
    ) -> None:
        """Initialize the ACB battery button entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        self._attr_unique_id = f"{self.envoy_serial_num}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self.envoy_serial_num}_acb")},
            manufacturer="Enphase",
            model="ACB",
            name=f"ACB {self.envoy_serial_num}",
            via_device=(DOMAIN, self.envoy_serial_num),
        )

    @exception_handler
    @override
    async def async_press(self) -> None:
        """Send the sleep or wake request for all ACB batteries."""
        acb_inventory = self.data.acb_inventory
        assert acb_inventory is not None
        low, high = self.coordinator.acb_sleep_soc()
        await self.entity_description.press_fn(
            self.envoy, list(acb_inventory), low, high
        )
        await self.coordinator.async_request_refresh()
