"""Support for Meshtastic settings that are numbers.

Both settings here are on the firmware's live list: changing
``lora.hop_limit`` or ``device.node_info_broadcast_secs`` leaves
``requiresReboot`` false in ``AdminModule::handleSetConfig`` and the node keeps
running.  The broadcast interval has a floor of one hour, which the firmware
enforces itself, so the entity refuses smaller values rather than letting the
node silently clamp them.
"""

from dataclasses import dataclass
from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeshtasticConfigEntry
from .config_entity import (
    SECTION_DEVICE,
    SECTION_LORA,
    MeshtasticConfigEntity,
    MeshtasticConfigSnapshot,
    async_get_config_snapshot,
)
from .coordinator import MeshtasticCoordinator

# Every write goes to the radio, which serves one admin message at a time.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MeshtasticNumberEntityDescription(NumberEntityDescription):
    """Describes a Meshtastic gateway configuration number."""

    section: str
    field: str


NUMBERS: tuple[MeshtasticNumberEntityDescription, ...] = (
    MeshtasticNumberEntityDescription(
        key="lora_hop_limit",
        translation_key="lora_hop_limit",
        section=SECTION_LORA,
        field="hop_limit",
        native_min_value=1,
        native_max_value=7,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
    MeshtasticNumberEntityDescription(
        key="device_node_info_broadcast_secs",
        translation_key="device_node_info_broadcast_secs",
        section=SECTION_DEVICE,
        field="node_info_broadcast_secs",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        # The firmware raises anything below an hour to the default itself
        # (Default.h:30), so offering smaller values would only mislead.
        native_min_value=3600,
        native_max_value=86400,
        native_step=60,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic numbers from a config entry."""
    coordinator = entry.runtime_data.coordinator
    snapshot = await async_get_config_snapshot(entry)
    async_add_entities(
        MeshtasticConfigNumber(coordinator, snapshot, description)
        for description in NUMBERS
    )


class MeshtasticConfigNumber(MeshtasticConfigEntity, NumberEntity):
    """A numeric gateway setting the firmware applies without rebooting."""

    entity_description: MeshtasticNumberEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        snapshot: MeshtasticConfigSnapshot,
        description: MeshtasticNumberEntityDescription,
    ) -> None:
        """Initialise a gateway configuration number."""
        super().__init__(
            coordinator,
            snapshot,
            key=description.key,
            section=description.section,
            field=description.field,
        )
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | None:
        """Return the value the node reported for this setting."""
        value = self.config_value
        return None if value is None else float(value)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the value and show it once the node acknowledged it."""
        await self.async_write_config(int(value))
        self.async_write_ha_state()
