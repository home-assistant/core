"""Button for Shelly."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from aioshelly.const import BLU_TRV_IDENTIFIER, MODEL_BLU_GATEWAY_G3, RPC_GENERATIONS
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError

from homeassistant.components.button import (
    DOMAIN as BUTTON_PLATFORM,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, MODEL_FRANKEVER_WATER_VALVE, SHELLY_GAS_MODELS
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    async_setup_entry_rpc,
    get_entity_block_device_info,
    get_entity_rpc_device_info,
    rpc_call,
)
from .utils import (
    async_remove_orphaned_entities,
    format_ble_addr,
    get_blu_trv_device_info,
    get_device_entry_gen,
    get_rpc_key_ids,
    get_rpc_key_instances,
    get_rpc_role_by_key,
    get_virtual_component_ids,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ShellyButtonDescription[
    _ShellyCoordinatorT: ShellyBlockCoordinator | ShellyRpcCoordinator
](ButtonEntityDescription):
    """Class to describe a Button entity."""

    press_action: str

    supported: Callable[[_ShellyCoordinatorT], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class RpcButtonDescription(RpcEntityDescription, ButtonEntityDescription):
    """Class to describe a RPC button."""


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
        supported=lambda coordinator: coordinator.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription[ShellyBlockCoordinator](
        key="mute",
        name="Mute",
        translation_key="mute",
        entity_category=EntityCategory.CONFIG,
        press_action="trigger_shelly_gas_mute",
        supported=lambda coordinator: coordinator.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription[ShellyBlockCoordinator](
        key="unmute",
        name="Unmute",
        translation_key="unmute",
        entity_category=EntityCategory.CONFIG,
        press_action="trigger_shelly_gas_unmute",
        supported=lambda coordinator: coordinator.model in SHELLY_GAS_MODELS,
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

    for key in ("reboot", "self_test", "mute", "unmute"):
        old_unique_id = f"{coordinator.mac}_{key}"
        if entity_entry.unique_id == old_unique_id:
            new_unique_id = f"{coordinator.mac}-{key}"
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

    if not isinstance(coordinator, ShellyRpcCoordinator):
        return None

    if blutrv_key_ids := get_rpc_key_ids(coordinator.device.status, BLU_TRV_IDENTIFIER):
        for _id in blutrv_key_ids:
            key = f"{BLU_TRV_IDENTIFIER}:{_id}"
            ble_addr: str = coordinator.device.config[key]["addr"]
            old_unique_id = f"{ble_addr}_calibrate"
            if entity_entry.unique_id == old_unique_id:
                new_unique_id = f"{format_ble_addr(ble_addr)}-{key}-calibrate"
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

    if virtual_button_keys := get_rpc_key_instances(
        coordinator.device.config, "button"
    ):
        for key in virtual_button_keys:
            old_unique_id = f"{coordinator.mac}-{key}"
            if entity_entry.unique_id == old_unique_id:
                role = get_rpc_role_by_key(coordinator.device.config, key)
                new_unique_id = f"{coordinator.mac}-{key}-button_{role}"
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
    """Set up button entities."""
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

    entities: list[ShellyButton] = []

    entities.extend(
        ShellyButton(coordinator, button)
        for button in BUTTONS
        if button.supported(coordinator)
    )

    async_add_entities(entities)

    if not isinstance(coordinator, ShellyRpcCoordinator):
        return

    # add RPC buttons
    async_setup_entry_rpc(
        hass, config_entry, async_add_entities, RPC_BUTTONS, RpcVirtualButton
    )

    # the user can remove virtual components from the device configuration, so
    # we need to remove orphaned entities
    virtual_button_component_ids = get_virtual_component_ids(
        coordinator.device.config, BUTTON_PLATFORM
    )
    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        BUTTON_PLATFORM,
        virtual_button_component_ids,
    )


class ShellyBaseButton(
    CoordinatorEntity[ShellyRpcCoordinator | ShellyBlockCoordinator], ButtonEntity
):
    """Defines a Shelly base button."""

    _attr_has_entity_name = True
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

        self._attr_unique_id = f"{coordinator.mac}-{description.key}"
        if isinstance(coordinator, ShellyBlockCoordinator):
            self._attr_device_info = get_entity_block_device_info(coordinator)
        else:
            self._attr_device_info = get_entity_rpc_device_info(coordinator)

    async def _press_method(self) -> None:
        """Press method."""
        method = getattr(self.coordinator.device, self.entity_description.press_action)

        if TYPE_CHECKING:
            assert method is not None

        await method()


class ShellyBluTrvButton(ShellyRpcAttributeEntity, ButtonEntity):
    """Represent a Shelly BLU TRV button."""

    entity_description: RpcButtonDescription
    _id: int

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcEntityDescription,
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator, key, attribute, description)

        config = coordinator.device.config[key]
        ble_addr: str = config["addr"]
        fw_ver = coordinator.device.status[key].get("fw_ver")

        self._attr_unique_id = f"{format_ble_addr(ble_addr)}-{key}-{attribute}"
        self._attr_device_info = get_blu_trv_device_info(
            config, ble_addr, coordinator.mac, fw_ver
        )

    @rpc_call
    async def async_press(self) -> None:
        """Triggers the Shelly button press service."""
        await self.coordinator.device.trigger_blu_trv_calibration(self._id)


class RpcVirtualButton(ShellyRpcAttributeEntity, ButtonEntity):
    """Defines a Shelly RPC virtual component button."""

    entity_description: RpcButtonDescription
    _id: int

    @rpc_call
    async def async_press(self) -> None:
        """Triggers the Shelly button press service."""
        if TYPE_CHECKING:
            assert isinstance(self.coordinator, ShellyRpcCoordinator)

        await self.coordinator.device.button_trigger(self._id, "single_push")


RPC_BUTTONS = {
    "button_generic": RpcButtonDescription(
        key="button",
        role="generic",
    ),
    "button_open": RpcButtonDescription(
        key="button",
        entity_registry_enabled_default=False,
        role="open",
        models={MODEL_FRANKEVER_WATER_VALVE},
    ),
    "button_close": RpcButtonDescription(
        key="button",
        entity_registry_enabled_default=False,
        role="close",
        models={MODEL_FRANKEVER_WATER_VALVE},
    ),
    "calibrate": RpcButtonDescription(
        key="blutrv",
        name="Calibrate",
        translation_key="calibrate",
        entity_category=EntityCategory.CONFIG,
        entity_class=ShellyBluTrvButton,
        models={MODEL_BLU_GATEWAY_G3},
    ),
}
