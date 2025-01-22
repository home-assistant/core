"""Select platform for Enphase Envoy solar energy monitor."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pyenphase import Envoy, EnvoyDryContactSettings
from pyenphase.const import SupportedFeatures
from pyenphase.models.dry_contacts import DryContactAction, DryContactMode
from pyenphase.models.tariff import EnvoyStorageMode, EnvoyStorageSettings

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class EnvoyRelaySelectEntityDescription(SelectEntityDescription):
    """Describes an Envoy Dry Contact Relay select entity."""

    value_fn: Callable[[EnvoyDryContactSettings], str]
    update_fn: Callable[
        [Envoy, EnvoyDryContactSettings, str], Coroutine[Any, Any, dict[str, Any]]
    ]


@dataclass(frozen=True, kw_only=True)
class EnvoyStorageSettingsSelectEntityDescription(SelectEntityDescription):
    """Describes an Envoy storage settings select entity."""

    value_fn: Callable[[EnvoyStorageSettings], str]
    update_fn: Callable[[Envoy, str], Awaitable[dict[str, Any]]]


RELAY_MODE_MAP = {
    DryContactMode.MANUAL: "standard",
    DryContactMode.STATE_OF_CHARGE: "battery",
}
REVERSE_RELAY_MODE_MAP = {v: k for k, v in RELAY_MODE_MAP.items()}
RELAY_ACTION_MAP = {
    DryContactAction.APPLY: "powered",
    DryContactAction.SHED: "not_powered",
    DryContactAction.SCHEDULE: "schedule",
    DryContactAction.NONE: "none",
}
REVERSE_RELAY_ACTION_MAP = {v: k for k, v in RELAY_ACTION_MAP.items()}
MODE_OPTIONS = list(REVERSE_RELAY_MODE_MAP)
ACTION_OPTIONS = list(REVERSE_RELAY_ACTION_MAP)

STORAGE_MODE_MAP = {
    EnvoyStorageMode.BACKUP: "backup",
    EnvoyStorageMode.SELF_CONSUMPTION: "self_consumption",
    EnvoyStorageMode.SAVINGS: "savings",
}
REVERSE_STORAGE_MODE_MAP = {v: k for k, v in STORAGE_MODE_MAP.items()}
STORAGE_MODE_OPTIONS = list(REVERSE_STORAGE_MODE_MAP)

RELAY_ENTITIES = (
    EnvoyRelaySelectEntityDescription(
        key="mode",
        translation_key="relay_mode",
        options=MODE_OPTIONS,
        value_fn=lambda relay: RELAY_MODE_MAP[relay.mode],
        update_fn=lambda envoy, relay, value: envoy.update_dry_contact(
            {
                "id": relay.id,
                "mode": REVERSE_RELAY_MODE_MAP[value],
            }
        ),
    ),
    EnvoyRelaySelectEntityDescription(
        key="grid_action",
        translation_key="relay_grid_action",
        options=ACTION_OPTIONS,
        value_fn=lambda relay: RELAY_ACTION_MAP[relay.grid_action],
        update_fn=lambda envoy, relay, value: envoy.update_dry_contact(
            {
                "id": relay.id,
                "grid_action": REVERSE_RELAY_ACTION_MAP[value],
            }
        ),
    ),
    EnvoyRelaySelectEntityDescription(
        key="microgrid_action",
        translation_key="relay_microgrid_action",
        options=ACTION_OPTIONS,
        value_fn=lambda relay: RELAY_ACTION_MAP[relay.micro_grid_action],
        update_fn=lambda envoy, relay, value: envoy.update_dry_contact(
            {
                "id": relay.id,
                "micro_grid_action": REVERSE_RELAY_ACTION_MAP[value],
            }
        ),
    ),
    EnvoyRelaySelectEntityDescription(
        key="generator_action",
        translation_key="relay_generator_action",
        options=ACTION_OPTIONS,
        value_fn=lambda relay: RELAY_ACTION_MAP[relay.generator_action],
        update_fn=lambda envoy, relay, value: envoy.update_dry_contact(
            {
                "id": relay.id,
                "generator_action": REVERSE_RELAY_ACTION_MAP[value],
            }
        ),
    ),
)
STORAGE_MODE_ENTITY = EnvoyStorageSettingsSelectEntityDescription(
    key="storage_mode",
    translation_key="storage_mode",
    options=STORAGE_MODE_OPTIONS,
    value_fn=lambda storage_settings: STORAGE_MODE_MAP[storage_settings.mode],
    update_fn=lambda envoy, value: envoy.set_storage_mode(
        REVERSE_STORAGE_MODE_MAP[value]
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnphaseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Enphase Envoy select platform."""
    coordinator = config_entry.runtime_data
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    entities: list[SelectEntity] = []
    if envoy_data.dry_contact_settings:
        entities.extend(
            EnvoyRelaySelectEntity(coordinator, entity, relay)
            for entity in RELAY_ENTITIES
            for relay in envoy_data.dry_contact_settings
        )
    if (
        envoy_data.tariff
        and envoy_data.tariff.storage_settings
        and coordinator.envoy.supported_features & SupportedFeatures.ENCHARGE
    ):
        entities.append(
            EnvoyStorageSettingsSelectEntity(coordinator, STORAGE_MODE_ENTITY)
        )
    async_add_entities(entities)


class EnvoyRelaySelectEntity(EnvoyBaseEntity, SelectEntity):
    """Representation of an Enphase Enpower select entity."""

    entity_description: EnvoyRelaySelectEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyRelaySelectEntityDescription,
        relay_id: str,
    ) -> None:
        """Initialize the Enphase relay select entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        enpower = self.data.enpower
        assert enpower is not None
        serial_number = enpower.serial_number
        self._relay_id = relay_id
        self._attr_unique_id = f"{serial_number}_relay_{relay_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, relay_id)},
            manufacturer="Enphase",
            model="Dry contact relay",
            name=self.relay.load_name,
            sw_version=str(enpower.firmware_version),
            via_device=(DOMAIN, serial_number),
        )

    @property
    def relay(self) -> EnvoyDryContactSettings:
        """Return the relay object."""
        return self.data.dry_contact_settings[self._relay_id]

    @property
    def current_option(self) -> str:
        """Return the state of the Enpower switch."""
        return self.entity_description.value_fn(self.relay)

    async def async_select_option(self, option: str) -> None:
        """Update the relay."""
        await self.entity_description.update_fn(self.envoy, self.relay, option)
        await self.coordinator.async_request_refresh()


class EnvoyStorageSettingsSelectEntity(EnvoyBaseEntity, SelectEntity):
    """Representation of an Enphase storage settings select entity."""

    entity_description: EnvoyStorageSettingsSelectEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyStorageSettingsSelectEntityDescription,
    ) -> None:
        """Initialize the Enphase storage settings select entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        assert coordinator.envoy.data is not None
        if enpower := coordinator.envoy.data.enpower:
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
            # If no enpower device assign selects to Envoy itself
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
    def current_option(self) -> str:
        """Return the state of the select entity."""
        assert self.data.tariff is not None
        assert self.data.tariff.storage_settings is not None
        return self.entity_description.value_fn(self.data.tariff.storage_settings)

    async def async_select_option(self, option: str) -> None:
        """Update the relay."""
        await self.entity_description.update_fn(self.envoy, option)
        await self.coordinator.async_request_refresh()
