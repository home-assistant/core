"""Button entity for Electrolux Integration."""

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Concatenate, override

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.dw_appliance import DWAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.client.appliances.td_appliance import TDAppliance
from electrolux_group_developer_sdk.client.appliances.wd_appliance import WDAppliance
from electrolux_group_developer_sdk.client.appliances.wm_appliance import WMAppliance
from electrolux_group_developer_sdk.constants import (
    APPLIANCE_STATE_DELAYED_START,
    APPLIANCE_STATE_END_OF_CYCLE,
    APPLIANCE_STATE_IDLE,
    APPLIANCE_STATE_OFF,
    APPLIANCE_STATE_PAUSED,
    APPLIANCE_STATE_READY_TO_START,
    APPLIANCE_STATE_RUNNING,
)
from electrolux_group_developer_sdk.feature_constants import EXECUTE_COMMAND

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .util import convert_to_snake_case

_LOGGER = logging.getLogger(__name__)

type SupportedAppliance = (
    WMAppliance | WDAppliance | TDAppliance | DWAppliance | OVAppliance | SOAppliance
)


@dataclass(frozen=True, kw_only=True)
class ElectroluxButtonBaseDescription[T: SupportedAppliance, **P = []](
    ButtonEntityDescription
):
    """Custom button entity description for Electrolux buttons."""

    exists_fn: Callable[Concatenate[T, P], bool]
    available_fn: Callable[Concatenate[T, P], bool]
    command_fn: Callable[Concatenate[T, P], dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class ElectroluxButtonDescription[T: SupportedAppliance](
    ElectroluxButtonBaseDescription[T]
):
    """Custom button entity description for Electrolux buttons."""


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleButtonDescription[T: SupportedAppliance](
    ElectroluxButtonBaseDescription[T, [str]]
):
    """Custom button entity description for Electrolux buttons."""


ELECTROLUX_CARE_BUTTONS: tuple[
    ElectroluxButtonDescription[DWAppliance | WMAppliance | WDAppliance | TDAppliance],
    ...,
] = (
    ElectroluxButtonDescription(
        key="start",
        translation_key="start",
        exists_fn=lambda appliance: appliance.is_feature_supported(EXECUTE_COMMAND),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state()
            in (APPLIANCE_STATE_READY_TO_START, APPLIANCE_STATE_IDLE)
        ),
        command_fn=lambda appliance: appliance.get_start_command(),
    ),
    ElectroluxButtonDescription(
        key="pause",
        translation_key="pause",
        exists_fn=lambda appliance: appliance.is_feature_supported(EXECUTE_COMMAND),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state()
            in (APPLIANCE_STATE_RUNNING, APPLIANCE_STATE_DELAYED_START)
        ),
        command_fn=lambda appliance: appliance.get_pause_command(),
    ),
    ElectroluxButtonDescription(
        key="stop",
        translation_key="stop",
        exists_fn=lambda appliance: appliance.is_feature_supported(EXECUTE_COMMAND),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state() == APPLIANCE_STATE_PAUSED
        ),
        command_fn=lambda appliance: appliance.get_stop_command(),
    ),
    ElectroluxButtonDescription(
        key="resume",
        translation_key="resume",
        exists_fn=lambda appliance: appliance.is_feature_supported(EXECUTE_COMMAND),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state() == APPLIANCE_STATE_PAUSED
        ),
        command_fn=lambda appliance: appliance.get_resume_command(),
    ),
)

ELECTROLUX_OVEN_BUTTONS: tuple[ElectroluxButtonDescription[OVAppliance], ...] = (
    ElectroluxButtonDescription(
        key="start",
        translation_key="start",
        exists_fn=lambda appliance: appliance.is_feature_supported(EXECUTE_COMMAND),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state()
            in (
                APPLIANCE_STATE_READY_TO_START,
                APPLIANCE_STATE_IDLE,
                APPLIANCE_STATE_OFF,
                APPLIANCE_STATE_PAUSED,
            )
        ),
        command_fn=lambda appliance: appliance.get_start_command(),
    ),
    ElectroluxButtonDescription(
        key="stop",
        translation_key="stop",
        exists_fn=lambda appliance: appliance.is_feature_supported(EXECUTE_COMMAND),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state()
            in (
                APPLIANCE_STATE_PAUSED,
                APPLIANCE_STATE_RUNNING,
                APPLIANCE_STATE_END_OF_CYCLE,
                APPLIANCE_STATE_DELAYED_START,
            )
        ),
        command_fn=lambda appliance: appliance.get_stop_command(),
    ),
)

ELECTROLUX_SO_OVEN_BUTTONS: tuple[
    ElectroluxSubmoduleButtonDescription[SOAppliance], ...
] = (
    ElectroluxSubmoduleButtonDescription(
        key="start",
        translation_key="start",
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, EXECUTE_COMMAND
        ),
        available_fn=lambda appliance, cavity: (
            appliance.get_current_cavity_appliance_state(cavity)
            in (
                APPLIANCE_STATE_READY_TO_START,
                APPLIANCE_STATE_IDLE,
                APPLIANCE_STATE_OFF,
                APPLIANCE_STATE_PAUSED,
            )
        ),
        command_fn=lambda appliance, cavity: appliance.get_start_command(cavity),
    ),
    ElectroluxSubmoduleButtonDescription(
        key="stop",
        translation_key="stop",
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, EXECUTE_COMMAND
        ),
        available_fn=lambda appliance, cavity: (
            appliance.get_current_cavity_appliance_state(cavity)
            in (
                APPLIANCE_STATE_PAUSED,
                APPLIANCE_STATE_RUNNING,
                APPLIANCE_STATE_END_OF_CYCLE,
                APPLIANCE_STATE_DELAYED_START,
            )
        ),
        command_fn=lambda appliance, cavity: appliance.get_stop_command(cavity),
    ),
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, (WMAppliance, WDAppliance, TDAppliance, DWAppliance)):
        entities.extend(
            ElectroluxButton(appliance_data, coordinator, description)
            for description in ELECTROLUX_CARE_BUTTONS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, OVAppliance):
        entities.extend(
            ElectroluxButton(appliance_data, coordinator, description)
            for description in ELECTROLUX_OVEN_BUTTONS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, SOAppliance):
        entities.extend(
            ElectroluxSubmoduleButton(appliance_data, coordinator, description, cavity)
            for description in ELECTROLUX_SO_OVEN_BUTTONS
            for cavity in appliance_data.get_supported_cavities()
            if description.exists_fn(appliance_data, cavity)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set button entity for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxBaseButton[T: SupportedAppliance](
    ElectroluxBaseEntity[T], ButtonEntity
):
    """Base Electrolux button entity."""

    @override
    def _update_attr_state(self) -> bool:
        new_available = self._is_button_available()
        if self._attr_available != new_available:
            self._attr_available = new_available
            return True
        return False

    @property
    @override
    def available(self) -> bool:
        """Return true if the button can be pressed."""
        return self._is_button_available()

    @override
    async def async_press(self) -> None:
        """Handle the button press."""
        command = self._get_command()
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    @abstractmethod
    def _is_button_available(self) -> bool:
        """Return true if the button can be pressed."""

    @abstractmethod
    def _get_command(self) -> dict[str, Any]:
        """Return the command to send when the button is pressed."""


class ElectroluxButton[T: SupportedAppliance](ElectroluxBaseButton[T]):
    """Unified Electrolux button entity."""

    entity_description: ElectroluxButtonDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxButtonDescription[T],
    ) -> None:
        """Init button entity for Electrolux Integration."""
        super().__init__(appliance_data, coordinator, description.key)
        self.entity_description = description

    @override
    def _is_button_available(self) -> bool:
        """Return true if the button can be pressed."""
        if self._appliance_data.get_current_remote_control() != "ENABLED":
            return False
        return self.entity_description.available_fn(self._appliance_data)

    @override
    def _get_command(self) -> dict[str, Any]:
        """Return the command to send when the button is pressed."""
        return self.entity_description.command_fn(self._appliance_data)


class ElectroluxSubmoduleButton[T: SupportedAppliance](ElectroluxBaseButton[T]):
    """Unified Electrolux submodule button entity."""

    entity_description: ElectroluxSubmoduleButtonDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSubmoduleButtonDescription[T],
        cavity: str,
    ) -> None:
        """Init button entity for Electrolux Integration."""
        entity_key = f"{convert_to_snake_case(cavity)}_{description.key}"
        translation_key = (
            f"{convert_to_snake_case(cavity)}_{description.translation_key}"
        )
        super().__init__(appliance_data, coordinator, entity_key)

        self._cavity = cavity
        self.entity_description = description
        self._attr_translation_key = translation_key

    @override
    def _is_button_available(self) -> bool:
        """Return true if the button can be pressed."""
        if self._appliance_data.get_current_remote_control() != "ENABLED":
            return False
        return self.entity_description.available_fn(self._appliance_data, self._cavity)

    @override
    def _get_command(self) -> dict[str, Any]:
        """Return the command to send when the button is pressed."""
        return self.entity_description.command_fn(self._appliance_data, self._cavity)
