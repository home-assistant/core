"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DEVICE_MODEL_ACCOUNT, DEVICE_MODEL_POT, NON_TRANSFER_ACCOUNT_TYPES
from .coordinator import MonzoConfigEntry, MonzoCoordinator, MonzoData
from .entity import MonzoBaseEntity
from .helpers import get_account_name

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MonzoSensorEntityDescription(SensorEntityDescription):
    """Describes Monzo sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]


ACCOUNT_SENSORS = (
    MonzoSensorEntityDescription(
        key="balance",
        translation_key="balance",
        value_fn=lambda data: data["balance"]["balance"] / 100,
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
    ),
    MonzoSensorEntityDescription(
        key="total_balance",
        translation_key="total_balance",
        value_fn=lambda data: data["balance"]["total_balance"] / 100,
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
    ),
    MonzoSensorEntityDescription(
        key="spend_today",
        translation_key="spend_today",
        value_fn=lambda data: abs(data["balance"]["spend_today"]) / 100,
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
    ),
)

POT_SENSORS = (
    MonzoSensorEntityDescription(
        key="pot_balance",
        translation_key="pot_balance",
        value_fn=lambda data: data["balance"] / 100,
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonzoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Monzo sensors and discover new resources."""
    coordinator = config_entry.runtime_data.coordinator

    known_account_ids: set[str] = set()
    known_pot_ids: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add sensors for newly discovered accounts and pots."""
        current_account_ids = set(coordinator.data.accounts)
        current_pot_ids = set(coordinator.data.pots)
        known_account_ids.intersection_update(current_account_ids)
        known_pot_ids.intersection_update(current_pot_ids)
        new_account_ids = current_account_ids - known_account_ids
        new_pot_ids = current_pot_ids - known_pot_ids
        if not new_account_ids and not new_pot_ids:
            return
        new_accounts = [
            (account_id, coordinator.data.accounts[account_id])
            for account_id in sorted(new_account_ids)
        ]
        new_pots = [
            (pot_id, coordinator.data.pots[pot_id]) for pot_id in sorted(new_pot_ids)
        ]

        async_add_entities(
            [
                MonzoSensor(
                    coordinator,
                    entity_description,
                    account_id,
                    (
                        account["name"]
                        if account["type"] in NON_TRANSFER_ACCOUNT_TYPES
                        else DEVICE_MODEL_ACCOUNT
                    ),
                    get_account_name(account),
                    account["balance"]["currency"],
                    lambda x: x.accounts,
                )
                for entity_description in ACCOUNT_SENSORS
                for account_id, account in new_accounts
            ]
            + [
                MonzoSensor(
                    coordinator,
                    entity_description,
                    pot_id,
                    DEVICE_MODEL_POT,
                    pot["name"],
                    pot["currency"],
                    lambda x: x.pots,
                )
                for entity_description in POT_SENSORS
                for pot_id, pot in new_pots
            ]
        )
        known_account_ids.update(new_account_ids)
        known_pot_ids.update(new_pot_ids)

    _async_add_new_entities()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_entities)
    )


class MonzoSensor(MonzoBaseEntity, SensorEntity):
    """Represents a Monzo sensor."""

    entity_description: MonzoSensorEntityDescription

    def __init__(
        self,
        coordinator: MonzoCoordinator,
        entity_description: MonzoSensorEntityDescription,
        resource_id: str,
        device_model: str,
        device_name: str,
        currency: str,
        data_accessor: Callable[[MonzoData], dict[str, dict[str, Any]]],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            resource_id,
            device_model,
            device_name,
            data_accessor,
        )
        self.entity_description = entity_description
        self._attr_native_unit_of_measurement = currency
        self._attr_unique_id = f"{resource_id}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state."""

        try:
            state = self.entity_description.value_fn(self.data)
        except KeyError, ValueError:
            return None

        return state
