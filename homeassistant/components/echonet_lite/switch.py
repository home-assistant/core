"""Switch platform for the HEMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pyhems.definitions import EntityDefinition, create_binary_decoder

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import (
    EchonetLiteDescribedEntity,
    EchonetLiteEntityDescription,
    setup_echonet_lite_platform,
)
from .types import EchonetLiteConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EchonetLiteSwitchEntityDescription(
    SwitchEntityDescription, EchonetLiteEntityDescription
):
    """Entity description that also stores EPC metadata."""

    decoder: Callable[[bytes], bool | None] = lambda _: None
    on_value: bytes  # Byte value for ON command
    off_value: bytes  # Byte value for OFF command
    require_write: bool | None = True  # Switch: must be writable


def _create_switch_description(
    class_code: int,
    entity_def: EntityDefinition,
) -> EchonetLiteSwitchEntityDescription:
    """Create a switch entity description from an EntityDefinition."""
    on_value, off_value = entity_def.get_binary_values()

    return EchonetLiteSwitchEntityDescription(
        key=f"{entity_def.epc:02x}",
        translation_key=entity_def.id,
        class_code=class_code,
        epc=entity_def.epc,
        device_class=None,
        decoder=create_binary_decoder(on_value),
        on_value=on_value,
        off_value=off_value,
        manufacturer_code=entity_def.manufacturer_code,
        fallback_name=entity_def.name_en or None,
    )


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EchonetLiteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ECHONET Lite switches from a config entry."""
    setup_echonet_lite_platform(
        entry,
        async_add_entities,
        "binary",
        _create_switch_description,
        EchonetLiteSwitch,
        "switch",
    )


class EchonetLiteSwitch(
    EchonetLiteDescribedEntity[EchonetLiteSwitchEntityDescription], SwitchEntity
):
    """Representation of a writable ECHONET Lite property."""

    @property
    def is_on(self) -> bool | None:
        """Return the decoded boolean value stored in the coordinator."""
        state = self._node.properties.get(self._epc)
        return self.description.decoder(state) if state else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the On command via the pyhems runtime client."""
        await self._async_send_property(self._epc, self.description.on_value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the Off command via the pyhems runtime client."""
        await self._async_send_property(self._epc, self.description.off_value)


__all__ = ["EchonetLiteSwitch"]
