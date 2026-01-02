"""Select platform for HDFury Integration."""

from abc import abstractmethod
from dataclasses import dataclass

from hdfury import OPERATION_MODES, TX0_INPUT_PORTS, TX1_INPUT_PORTS, HDFuryError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import HDFuryConfigEntry, HDFuryCoordinator
from .entity import HDFuryEntity


@dataclass(kw_only=True, frozen=True)
class HDFurySelectEntityDescription(SelectEntityDescription):
    """Description for HDFury select entities."""

    label_map: dict[str, str]
    reverse_map: dict[str, str]


SELECT_PORTS: tuple[HDFurySelectEntityDescription, ...] = (
    HDFurySelectEntityDescription(
        key="portseltx0",
        translation_key="portseltx",
        translation_placeholders={"port": "0"},
        options=list(TX0_INPUT_PORTS.values()),
        label_map=TX0_INPUT_PORTS,
        reverse_map={v: k for k, v in TX0_INPUT_PORTS.items()},
    ),
    HDFurySelectEntityDescription(
        key="portseltx1",
        translation_key="portseltx",
        translation_placeholders={"port": "1"},
        options=list(TX1_INPUT_PORTS.values()),
        label_map=TX1_INPUT_PORTS,
        reverse_map={v: k for k, v in TX1_INPUT_PORTS.items()},
    ),
)


SELECT_OPERATION_MODE: HDFurySelectEntityDescription = HDFurySelectEntityDescription(
    key="opmode",
    translation_key="opmode",
    options=list(OPERATION_MODES.values()),
    label_map=OPERATION_MODES,
    reverse_map={v: k for k, v in OPERATION_MODES.items()},
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HDFuryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects using the platform schema."""

    coordinator: HDFuryCoordinator = entry.runtime_data

    entities: list[HDFuryEntity] = []

    for description in SELECT_PORTS:
        if description.key not in coordinator.data.info:
            continue

        entities.append(HDFuryPortSelect(coordinator, description))

    # Add OPMODE select if present
    if "opmode" in coordinator.data.info:
        entities.append(HDFuryOpModeSelect(coordinator, SELECT_OPERATION_MODE))

    async_add_entities(entities)


class HDFuryBaseSelect(HDFuryEntity, SelectEntity):
    """HDFury Select Class."""

    entity_description: HDFurySelectEntityDescription

    @property
    def current_option(self) -> str:
        """Return the current option."""

        raw_value = self.coordinator.data.info[self.entity_description.key]
        return self.entity_description.label_map[raw_value]

    async def async_select_option(self, option: str) -> None:
        """Update the current option."""

        raw_value = self.entity_description.reverse_map[option]

        # Update local data first
        self.coordinator.data.info[self.entity_description.key] = raw_value

        # Send command to device
        try:
            await self._set_option(raw_value)
        except HDFuryError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        # Trigger HA state write
        self.async_write_ha_state()

    @abstractmethod
    async def _set_option(self, value: str) -> None:
        """Apply value to device."""


class HDFuryPortSelect(HDFuryBaseSelect):
    """Handle port selection (portseltx)."""

    async def _set_option(self, value: str) -> None:
        """Apply value to device."""

        tx0 = self.coordinator.data.info.get("portseltx0")
        tx1 = self.coordinator.data.info.get("portseltx1")

        if tx0 is None or tx1 is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="tx_state_error",
                translation_placeholders={"details": f"tx0={tx0}, tx1={tx1}"},
            )

        await self.coordinator.client.set_port_selection(tx0, tx1)


class HDFuryOpModeSelect(HDFuryBaseSelect):
    """Handle operation mode selection (opmode)."""

    async def _set_option(self, value: str) -> None:
        """Apply value to device."""

        await self.coordinator.client.set_operation_mode(value)
