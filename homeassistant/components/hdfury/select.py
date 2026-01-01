"""Select platform for HDFury Integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from hdfury import (
    OPERATION_MODES,
    TX0_INPUT_PORTS,
    TX1_INPUT_PORTS,
    HDFuryAPI,
    HDFuryError,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import HDFuryConfigEntry, HDFuryCoordinator
from .entity import HDFuryEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class HDFurySelectPortEntityDescription(SelectEntityDescription):
    """Description for HDFury select port entities."""

    label_map: dict[str, str]
    reverse_map: dict[str, str]
    set_value_fn: Callable[[HDFuryAPI, str, str], Awaitable[None]]


@dataclass(kw_only=True, frozen=True)
class HDFurySelectOperationEntityDescription(SelectEntityDescription):
    """Description for HDFury select operation entities."""

    label_map: dict[str, str]
    reverse_map: dict[str, str]
    set_value_fn: Callable[[HDFuryAPI, str], Awaitable[None]]


SELECT_PORTS: tuple[HDFurySelectPortEntityDescription, ...] = (
    HDFurySelectPortEntityDescription(
        key="portseltx0",
        translation_key="portseltx0",
        options=list(TX0_INPUT_PORTS.values()),
        label_map=TX0_INPUT_PORTS,
        reverse_map={v: k for k, v in TX0_INPUT_PORTS.items()},
        set_value_fn=lambda client, tx0_value, tx1_value: client.set_port_selection(
            tx0_value, tx1_value
        ),
    ),
    HDFurySelectPortEntityDescription(
        key="portseltx1",
        translation_key="portseltx1",
        options=list(TX1_INPUT_PORTS.values()),
        label_map=TX1_INPUT_PORTS,
        reverse_map={v: k for k, v in TX1_INPUT_PORTS.items()},
        set_value_fn=lambda client, tx0_value, tx1_value: client.set_port_selection(
            tx0_value, tx1_value
        ),
    ),
)


SELECT_OPERATION_MODE: HDFurySelectOperationEntityDescription = (
    HDFurySelectOperationEntityDescription(
        key="opmode",
        translation_key="opmode",
        options=list(OPERATION_MODES.values()),
        label_map=OPERATION_MODES,
        reverse_map={v: k for k, v in OPERATION_MODES.items()},
        set_value_fn=lambda client, value: client.set_operation_mode(value),
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HDFuryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects using the platform schema."""

    coordinator: HDFuryCoordinator = entry.runtime_data

    # Load custom labels if present
    custom_labels: dict[str, str] = entry.options.get("option_labels", {})

    entities: list[HDFuryEntity] = []

    # Apply custom labels for port selectors
    for description in SELECT_PORTS:
        if description.key not in coordinator.data["info"]:
            continue

        # Build label maps with custom labels applied
        label_map = {
            k: custom_labels.get(v, v) for k, v in description.label_map.items()
        }
        reverse_map = {v: k for k, v in label_map.items()}

        # Create a new description object with overridden maps
        desc = HDFurySelectPortEntityDescription(
            key=description.key,
            translation_key=description.translation_key,
            options=list(label_map.values()),
            label_map=label_map,
            reverse_map=reverse_map,
            set_value_fn=description.set_value_fn,
        )

        entities.append(HDFuryPortSelect(coordinator, desc))

    # Add OPMODE select if present
    if "opmode" in coordinator.data["info"]:
        entities.append(HDFuryOpModeSelect(coordinator, SELECT_OPERATION_MODE))

    async_add_entities(entities)


class HDFuryPortSelect(HDFuryEntity, SelectEntity):
    """Class to handle fetching and storing HDFury Port Select data."""

    entity_description: HDFurySelectPortEntityDescription

    @property
    def current_option(self) -> str | None:
        """Set Current Select Option."""

        raw_value = self.coordinator.data["info"].get(self.entity_description.key)
        return self.entity_description.label_map.get(raw_value)

    async def async_select_option(self, option: str) -> None:
        """Handle Port Select."""

        # Map user-friendly label back to raw input value
        raw_value = self.entity_description.reverse_map.get(option)
        if raw_value is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="data_error",
                translation_placeholders={
                    "error": str(f"Invalid input option selected: {option}")
                },
            )

        # Update local data first
        self.coordinator.data["info"][self.entity_description.key] = raw_value

        # Remap both TX0 and TX1 current selections
        tx0_raw = self.coordinator.data["info"].get("portseltx0")
        tx1_raw = self.coordinator.data["info"].get("portseltx1")

        # If either missing, raise exception to avoid incomplete updates
        if tx0_raw is None or tx1_raw is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="data_error",
                translation_placeholders={
                    "error": str(f"TX states incomplete: tx0={tx0_raw}, tx1={tx1_raw}")
                },
            )

        # Send command to device
        try:
            await self.entity_description.set_value_fn(
                self.coordinator.client, tx0_raw, tx1_raw
            )
        except HDFuryError as error:
            _LOGGER.error("%s", error)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        # Trigger HA state refresh
        await self.coordinator.async_request_refresh()


class HDFuryOpModeSelect(HDFuryEntity, SelectEntity):
    """Handle operation mode selection (opmode)."""

    entity_description: HDFurySelectOperationEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the current operation mode."""

        raw_value = self.coordinator.data["info"].get(self.entity_description.key)
        return self.entity_description.label_map.get(raw_value)

    async def async_select_option(self, option: str) -> None:
        """Change the operation mode."""

        # Map user-friendly label back to raw input value
        raw_value = self.entity_description.reverse_map.get(option)
        if raw_value is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="data_error",
                translation_placeholders={
                    "error": str(f"Invalid input option selected: {option}")
                },
            )

        # Update local data first
        self.coordinator.data["info"][self.entity_description.key] = raw_value

        # Send command to device
        try:
            await self.entity_description.set_value_fn(
                self.coordinator.client, raw_value
            )
        except HDFuryError as error:
            _LOGGER.error("%s", error)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        # Trigger HA state refresh
        await self.coordinator.async_request_refresh()
