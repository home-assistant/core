"""Select platform for the HEMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HemsCoordinator
from .definitions import DecoderSpec, EntityDefinition, EnumDecoderSpec
from .entity import HemsDescribedEntity, HemsEntityDescription, setup_hems_platform
from .types import HemsConfigEntry, HemsNodeState

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HemsSelectEntityDescription(SelectEntityDescription, HemsEntityDescription):
    """Entity description that stores EPC metadata and value mapping."""

    decoder: Callable[[bytes], int | None]
    value_to_option: dict[int, str]
    option_to_value: dict[str, int]
    require_write: bool | None = True  # Select: must be writable


def _create_select_description(
    class_code: int,
    entity_def: EntityDefinition,
    decoder_spec: DecoderSpec,
) -> HemsSelectEntityDescription:
    """Create a select entity description from an EntityDefinition.

    All select entities in definitions.json are validated to have enum_values,
    so this function always returns a valid description.
    """
    assert isinstance(decoder_spec, EnumDecoderSpec)

    value_to_option: dict[int, str] = {}
    option_to_value: dict[str, int] = {}

    for edt_str, name in sorted(entity_def.enum_values.items()):
        value = int(edt_str)  # decimal string (e.g., "65")
        value_to_option[value] = name
        option_to_value[name] = value

    assert option_to_value, (
        f"Select entity EPC 0x{entity_def.epc:02X} for class 0x{class_code:04X} "
        "has no valid enum values - this should be caught during generation"
    )

    return HemsSelectEntityDescription(
        key=f"{entity_def.epc:02x}",
        translation_key=entity_def.translation_key,
        class_code=class_code,
        epc=entity_def.epc,
        decoder=decoder_spec.create_decoder(),
        value_to_option=value_to_option,
        option_to_value=option_to_value,
        manufacturer_code=entity_def.manufacturer_code,
        fallback_name=entity_def.fallback_name,
    )


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: HemsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HEMS select entities from a config entry."""
    setup_hems_platform(
        entry,
        async_add_entities,
        "select",
        _create_select_description,
        HemsSelect,
        "select",
    )


class HemsSelect(HemsDescribedEntity[HemsSelectEntityDescription], SelectEntity):
    """Representation of a writable ECHONET Lite select property."""

    def __init__(
        self,
        coordinator: HemsCoordinator,
        node: HemsNodeState,
        description: HemsSelectEntityDescription,
    ) -> None:
        """Initialize the HEMS select entity."""
        super().__init__(coordinator, node, description)
        self._attr_options = list(description.option_to_value)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option or None if unset.

        The raw property value is decoded and mapped to the option name.
        """
        if (state := self._node.properties.get(self._epc)) is None:
            return None
        if (value := self.description.decoder(state)) is None:
            return None
        return self.description.value_to_option.get(value)

    async def async_select_option(self, option: str) -> None:
        """Select the given option by sending the corresponding payload."""
        if (value := self.description.option_to_value.get(option)) is None:
            raise ValueError(f"Unsupported option: {option}")
        await self._async_send_property(self._epc, bytes([value]))
