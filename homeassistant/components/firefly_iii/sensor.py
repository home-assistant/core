"""Sensor platform for Firefly III integration."""

from __future__ import annotations

from collections.abc import Callable
import logging

from pyfirefly.models import Account, Bill, Budget, Category, Transaction

from homeassistant.components.firefly_iii.entity import FireflyAccountEntity
from homeassistant.components.http import dataclass
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.todo import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class FireflySensorEntityDescription(SensorEntityDescription):
    """Class to hold Firefly sensor description."""

    value_fn: Callable[[Category, Account, Transaction, Budget, Bill], StateType]
    # TODO: Check if I want to do something with attributes_fn


ACCOUNT_SENSORS: tuple[FireflySensorEntityDescription, ...] = (
    FireflySensorEntityDescription(
        key="account",
        value_fn=lambda account: float(account.native_current_balance),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Firefly III sensor platform."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for account in coordinator.data.accounts:
        entities.extend(
            [
                FireflyAccountEntity(
                    coordinator=coordinator,
                    entity_description=description,
                    account=account,
                )
                for description in ACCOUNT_SENSORS
            ]
        )

    async_add_entities(entities)
