"""Switch platform for Enphase Envoy solar energy monitor."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pyenphase import Envoy, EnvoyDryContactStatus, EnvoyEnpower
from pyenphase.const import SupportedFeatures
from pyenphase.models.dry_contacts import DryContactStatus
from pyenphase.models.tariff import EnvoyStorageSettings

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity, exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class EnvoyEnpowerSwitchEntityDescription(SwitchEntityDescription):
    """Describes an Envoy Enpower switch entity."""

    value_fn: Callable[[EnvoyEnpower], bool]
    turn_on_fn: Callable[[Envoy], Coroutine[Any, Any, dict[str, Any]]]
    turn_off_fn: Callable[[Envoy], Coroutine[Any, Any, dict[str, Any]]]


@dataclass(frozen=True, kw_only=True)
class EnvoyDryContactSwitchEntityDescription(SwitchEntityDescription):
    """Describes an Envoy Enpower dry contact switch entity."""

    value_fn: Callable[[EnvoyDryContactStatus], bool]
    turn_on_fn: Callable[[Envoy, str], Coroutine[Any, Any, dict[str, Any]]]
    turn_off_fn: Callable[[Envoy, str], Coroutine[Any, Any, dict[str, Any]]]


@dataclass(frozen=True, kw_only=True)
class EnvoyStorageSettingsSwitchEntityDescription(SwitchEntityDescription):
    """Describes an Envoy storage settings switch entity."""

    value_fn: Callable[[EnvoyStorageSettings], bool]
    turn_on_fn: Callable[[Envoy], Awaitable[dict[str, Any]]]
    turn_off_fn: Callable[[Envoy], Awaitable[dict[str, Any]]]


ENPOWER_GRID_SWITCH = EnvoyEnpowerSwitchEntityDescription(
    key="mains_admin_state",
    translation_key="grid_enabled",
    value_fn=lambda enpower: enpower.mains_admin_state == "closed",
    turn_on_fn=lambda envoy: envoy.go_on_grid(),
    turn_off_fn=lambda envoy: envoy.go_off_grid(),
)

RELAY_STATE_SWITCH = EnvoyDryContactSwitchEntityDescription(
    key="relay_status",
    translation_key="relay_status",
    value_fn=lambda dry_contact: dry_contact.status == DryContactStatus.CLOSED,
    turn_on_fn=lambda envoy, id: envoy.close_dry_contact(id),
    turn_off_fn=lambda envoy, id: envoy.open_dry_contact(id),
)

CHARGE_FROM_GRID_SWITCH = EnvoyStorageSettingsSwitchEntityDescription(
    key="charge_from_grid",
    translation_key="charge_from_grid",
    value_fn=lambda storage_settings: storage_settings.charge_from_grid,
    turn_on_fn=lambda envoy: envoy.enable_charge_from_grid(),
    turn_off_fn=lambda envoy: envoy.disable_charge_from_grid(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnphaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Enphase Envoy switch platform."""
    coordinator = config_entry.runtime_data
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    entities: list[SwitchEntity] = []
    if envoy_data.enpower:
        entities.extend(
            [
                EnvoyEnpowerSwitchEntity(
                    coordinator, ENPOWER_GRID_SWITCH, envoy_data.enpower
                )
            ]
        )

    if envoy_data.dry_contact_status:
        entities.extend(
            EnvoyDryContactSwitchEntity(coordinator, RELAY_STATE_SWITCH, relay)
            for relay in envoy_data.dry_contact_status
        )

    if (
        envoy_data.tariff
        and envoy_data.tariff.storage_settings
        and (coordinator.envoy.supported_features & SupportedFeatures.ENCHARGE)
    ):
        entities.append(
            EnvoyStorageSettingsSwitchEntity(
                coordinator, CHARGE_FROM_GRID_SWITCH, envoy_data.enpower
            )
        )

    async_add_entities(entities)


class EnvoyEnpowerSwitchEntity(EnvoyBaseEntity, SwitchEntity):
    """Representation of an Enphase Enpower switch entity."""

    entity_description: EnvoyEnpowerSwitchEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyEnpowerSwitchEntityDescription,
        enpower: EnvoyEnpower,
    ) -> None:
        """Initialize the Enphase Enpower switch entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        self.enpower = enpower
        self._serial_number = enpower.serial_number
        self._attr_unique_id = f"{self._serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            manufacturer="Enphase",
            model="Enpower",
            name=f"Enpower {self._serial_number}",
            sw_version=str(enpower.firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the Enpower switch."""
        enpower = self.data.enpower
        assert enpower is not None
        return self.entity_description.value_fn(enpower)

    @exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Enpower switch."""
        await self.entity_description.turn_on_fn(self.envoy)
        await self.coordinator.async_request_refresh()

    @exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Enpower switch."""
        await self.entity_description.turn_off_fn(self.envoy)
        await self.coordinator.async_request_refresh()


class EnvoyDryContactSwitchEntity(EnvoyBaseEntity, SwitchEntity):
    """Representation of an Enphase dry contact switch entity."""

    entity_description: EnvoyDryContactSwitchEntityDescription
    _attr_name = None

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyDryContactSwitchEntityDescription,
        relay_id: str,
    ) -> None:
        """Initialize the Enphase dry contact switch entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        enpower = self.data.enpower
        assert enpower is not None
        self.relay_id = relay_id
        serial_number = enpower.serial_number
        self._attr_unique_id = f"{serial_number}_relay_{relay_id}_{description.key}"
        relay = self.data.dry_contact_settings[relay_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, relay_id)},
            manufacturer="Enphase",
            model="Dry contact relay",
            name=relay.load_name,
            sw_version=str(enpower.firmware_version),
            via_device=(DOMAIN, enpower.serial_number),
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the dry contact."""
        relay = self.data.dry_contact_status[self.relay_id]
        assert relay is not None
        return self.entity_description.value_fn(relay)

    @exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on (close) the dry contact."""
        if await self.entity_description.turn_on_fn(self.envoy, self.relay_id):
            self.async_write_ha_state()

    @exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off (open) the dry contact."""
        if await self.entity_description.turn_off_fn(self.envoy, self.relay_id):
            self.async_write_ha_state()


class EnvoyStorageSettingsSwitchEntity(EnvoyBaseEntity, SwitchEntity):
    """Representation of an Enphase storage settings switch entity."""

    entity_description: EnvoyStorageSettingsSwitchEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyStorageSettingsSwitchEntityDescription,
        enpower: EnvoyEnpower | None,
    ) -> None:
        """Initialize the Enphase storage settings switch entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        self.enpower = enpower
        if enpower:
            self._serial_number = enpower.serial_number
            self._attr_unique_id = f"{self._serial_number}_{description.key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._serial_number)},
                manufacturer="Enphase",
                model="Enpower",
                name=f"Enpower {self._serial_number}",
                sw_version=str(enpower.firmware_version),
                via_device=(DOMAIN, self.envoy_serial_num),
            )
        else:
            # If no enpower device assign switches to Envoy itself
            self._attr_unique_id = f"{self.envoy_serial_num}_{description.key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.envoy_serial_num)},
                manufacturer="Enphase",
                model=coordinator.envoy.envoy_model,
                name=coordinator.name,
                sw_version=str(coordinator.envoy.firmware),
                hw_version=coordinator.envoy.part_number,
                serial_number=self.envoy_serial_num,
            )

    @property
    def is_on(self) -> bool:
        """Return the state of the storage settings switch."""
        assert self.data.tariff is not None
        assert self.data.tariff.storage_settings is not None
        return self.entity_description.value_fn(self.data.tariff.storage_settings)

    @exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the storage settings switch."""
        await self.entity_description.turn_on_fn(self.envoy)
        await self.coordinator.async_request_refresh()

    @exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the storage switch."""
        await self.entity_description.turn_off_fn(self.envoy)
        await self.coordinator.async_request_refresh()
