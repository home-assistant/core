"""Number platform for Palazzetti settings."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pypalazzetti.exceptions import CommunicationError, ValidationError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PalazzettiConfigEntry
from .const import DOMAIN
from .coordinator import PalazzettiDataUpdateCoordinator
from .entity import PalazzettiEntity

MIN_POWER = 1
MAX_POWER = 5


@dataclass(frozen=True, kw_only=True)
class PalazzettiNumberEntityDescription(NumberEntityDescription):
    """Describes Palazzetti number entity."""

    value_property: str
    update_fn: Callable[[int], Coroutine[Any, Any, None]]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PalazzettiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Palazzetti number platform."""
    client = config_entry.runtime_data.client

    async_add_entities(
        [
            PalazzettiNumberEntity(
                config_entry.runtime_data,
                PalazzettiNumberEntityDescription(
                    key="combustion_power",
                    translation_key="combustion_power",
                    device_class=NumberDeviceClass.POWER_FACTOR,
                    native_min_value=MIN_POWER,
                    native_max_value=MAX_POWER,
                    native_step=1,
                    value_property="power_mode",
                    update_fn=client.set_power_mode,
                ),
                config_entry.entry_id,
            )
        ]
    )


class PalazzettiNumberEntity(PalazzettiEntity, NumberEntity):
    """Representation of Palazzetti number entity."""

    entity_description: PalazzettiNumberEntityDescription

    def __init__(
        self,
        coordinator: PalazzettiDataUpdateCoordinator,
        description: PalazzettiNumberEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the Palazzetti number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-{description.key}"

    @property
    def native_value(self) -> float:
        """Return the state of the setting entity."""
        client = self.coordinator.client
        return getattr(client, self.entity_description.value_property)

    async def async_set_native_value(self, value: float) -> None:
        """Update the setting."""
        try:
            await self.entity_description.update_fn(int(value))
        except CommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except ValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_combustion_power",
                translation_placeholders={
                    "value": str(value),
                },
            ) from err

        await self.coordinator.async_request_refresh()
