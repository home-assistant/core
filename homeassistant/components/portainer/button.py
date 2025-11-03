"""Support for Portainer buttons."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from pyportainer import Portainer
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
from pyportainer.models.docker import DockerContainer

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PortainerConfigEntry
from .const import DOMAIN
from .coordinator import PortainerCoordinator, PortainerCoordinatorData
from .entity import PortainerContainerEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PortainerButtonDescription(ButtonEntityDescription):
    """Class to describe a Portainer button entity."""

    press_action: Callable[
        [Portainer, int, str],
        Coroutine[Any, Any, None],
    ]


BUTTONS: tuple[PortainerButtonDescription, ...] = (
    PortainerButtonDescription(
        key="restart",
        name="Restart Container",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=(
            lambda portainer, endpoint_id, container_id: portainer.restart_container(
                endpoint_id, container_id
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer buttons."""
    coordinator: PortainerCoordinator = entry.runtime_data

    async_add_entities(
        PortainerButton(
            coordinator=coordinator,
            entity_description=entity_description,
            device_info=container,
            via_device=endpoint,
        )
        for endpoint in coordinator.data.values()
        for container in endpoint.containers.values()
        for entity_description in BUTTONS
    )


class PortainerButton(PortainerContainerEntity, ButtonEntity):
    """Defines a Portainer button."""

    entity_description: PortainerButtonDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerButtonDescription,
        device_info: DockerContainer,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer button entity."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"

    async def async_press(self) -> None:
        """Trigger the Portainer button press service."""
        try:
            await self.entity_description.press_action(
                self.coordinator.portainer, self.endpoint_id, self.device_id
            )
        except PortainerConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except PortainerAuthenticationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except PortainerTimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
