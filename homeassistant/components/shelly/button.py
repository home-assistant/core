"""Button for Shelly."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from aioshelly.const import BLU_TRV_IDENTIFIER, MODEL_BLU_GATEWAY, RPC_GENERATIONS
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, LOGGER, SHELLY_GAS_MODELS
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .utils import get_device_entry_gen, get_rpc_key_ids


@dataclass(frozen=True, kw_only=True)
class ShellyButtonDescription[
    _ShellyCoordinatorT: ShellyBlockCoordinator | ShellyRpcCoordinator
](ButtonEntityDescription):
    """Class to describe a Button entity."""

    press_action: str

    supported: Callable[[_ShellyCoordinatorT], bool] = lambda _: True


BUTTONS: Final[list[ShellyButtonDescription[Any]]] = [
    ShellyButtonDescription[ShellyBlockCoordinator | ShellyRpcCoordinator](
        key="reboot",
        name="Reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action="trigger_reboot",
    ),
    ShellyButtonDescription[ShellyBlockCoordinator](
        key="self_test",
        name="Self test",
        translation_key="self_test",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action="trigger_shelly_gas_self_test",
        supported=lambda coordinator: coordinator.device.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription[ShellyBlockCoordinator](
        key="mute",
        name="Mute",
        translation_key="mute",
        entity_category=EntityCategory.CONFIG,
        press_action="trigger_shelly_gas_mute",
        supported=lambda coordinator: coordinator.device.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription[ShellyBlockCoordinator](
        key="unmute",
        name="Unmute",
        translation_key="unmute",
        entity_category=EntityCategory.CONFIG,
        press_action="trigger_shelly_gas_unmute",
        supported=lambda coordinator: coordinator.device.model in SHELLY_GAS_MODELS,
    ),
]

BLU_TRV_BUTTONS: Final[list[ShellyButtonDescription]] = [
    ShellyButtonDescription[ShellyRpcCoordinator](
        key="calibrate",
        name="Calibrate",
        translation_key="calibrate",
        entity_category=EntityCategory.CONFIG,
        press_action="trigger_blu_trv_calibration",
        supported=lambda coordinator: coordinator.device.model == MODEL_BLU_GATEWAY,
    ),
]


@callback
def async_migrate_unique_ids(
    coordinator: ShellyRpcCoordinator | ShellyBlockCoordinator,
    entity_entry: er.RegistryEntry,
) -> dict[str, Any] | None:
    """Migrate button unique IDs."""
    if not entity_entry.entity_id.startswith("button"):
        return None

    device_name = slugify(coordinator.device.name)

    for key in ("reboot", "self_test", "mute", "unmute"):
        old_unique_id = f"{device_name}_{key}"
        if entity_entry.unique_id == old_unique_id:
            new_unique_id = f"{coordinator.mac}_{key}"
            LOGGER.debug(
                "Migrating unique_id for %s entity from [%s] to [%s]",
                entity_entry.entity_id,
                old_unique_id,
                new_unique_id,
            )
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old_unique_id, new_unique_id
                )
            }

    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set buttons for device."""
    entry_data = config_entry.runtime_data
    coordinator: ShellyRpcCoordinator | ShellyBlockCoordinator | None
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        coordinator = entry_data.rpc
    else:
        coordinator = entry_data.block

    if TYPE_CHECKING:
        assert coordinator is not None

    await er.async_migrate_entries(
        hass, config_entry.entry_id, partial(async_migrate_unique_ids, coordinator)
    )

    entities: list[ShellyButton | ShellyBluTrvButton] = []

    entities.extend(
        ShellyButton(coordinator, button)
        for button in BUTTONS
        if button.supported(coordinator)
    )

    if blutrv_key_ids := get_rpc_key_ids(coordinator.device.status, BLU_TRV_IDENTIFIER):
        if TYPE_CHECKING:
            assert isinstance(coordinator, ShellyRpcCoordinator)

        entities.extend(
            ShellyBluTrvButton(coordinator, button, id_)
            for id_ in blutrv_key_ids
            for button in BLU_TRV_BUTTONS
        )

    async_add_entities(entities)


class ShellyBaseButton(
    CoordinatorEntity[ShellyRpcCoordinator | ShellyBlockCoordinator], ButtonEntity
):
    """Defines a Shelly base button."""

    entity_description: ShellyButtonDescription[
        ShellyRpcCoordinator | ShellyBlockCoordinator
    ]

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator | ShellyBlockCoordinator,
        description: ShellyButtonDescription[
            ShellyRpcCoordinator | ShellyBlockCoordinator
        ],
    ) -> None:
        """Initialize Shelly button."""
        super().__init__(coordinator)

        self.entity_description = description

    async def async_press(self) -> None:
        """Triggers the Shelly button press service."""
        try:
            await self._press_method()
        except DeviceConnectionError as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_communication_action_error",
                translation_placeholders={
                    "entity": self.entity_id,
                    "device": self.coordinator.name,
                },
            ) from err
        except RpcCallError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rpc_call_action_error",
                translation_placeholders={
                    "entity": self.entity_id,
                    "device": self.coordinator.name,
                },
            ) from err
        except InvalidAuthError:
            await self.coordinator.async_shutdown_device_and_start_reauth()

    async def _press_method(self) -> None:
        """Press method."""
        raise NotImplementedError


class ShellyButton(ShellyBaseButton):
    """Defines a Shelly button."""

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator | ShellyBlockCoordinator,
        description: ShellyButtonDescription[
            ShellyRpcCoordinator | ShellyBlockCoordinator
        ],
    ) -> None:
        """Initialize Shelly button."""
        super().__init__(coordinator, description)

        self._attr_name = f"{coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{coordinator.mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)}
        )

    async def _press_method(self) -> None:
        """Press method."""
        method = getattr(self.coordinator.device, self.entity_description.press_action)

        if TYPE_CHECKING:
            assert method is not None

        await method()


class ShellyBluTrvButton(ShellyBaseButton):
    """Represent a Shelly BLU TRV button."""

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        description: ShellyButtonDescription,
        id_: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)

        ble_addr: str = coordinator.device.config[f"{BLU_TRV_IDENTIFIER}:{id_}"]["addr"]
        device_name = (
            coordinator.device.config[f"{BLU_TRV_IDENTIFIER}:{id_}"]["name"]
            or f"shellyblutrv-{ble_addr.replace(':', '')}"
        )
        self._attr_name = f"{device_name} {description.name}"
        self._attr_unique_id = f"{ble_addr}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, ble_addr)}
        )
        self._id = id_

    async def _press_method(self) -> None:
        """Press method."""
        method = getattr(self.coordinator.device, self.entity_description.press_action)

        if TYPE_CHECKING:
            assert method is not None

        await method(self._id)
