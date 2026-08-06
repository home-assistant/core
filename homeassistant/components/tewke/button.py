"""Button platform for the Tewke integration.

Exposes a restart (reboot) button for the Tewke Tap Panel.
"""

from typing import TYPE_CHECKING, override

from pytewke.error import (
    PyTewkeCoapError,
    PyTewkeInvalidRequestError,
    PyTewkeUnknownError,
)

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import TewkeEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import TewkeCoordinator
    from .data import TewkeConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TewkeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tewke button entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([TewkeRestartButton(coordinator=coordinator)])


class TewkeRestartButton(TewkeEntity, ButtonEntity):
    """Button entity to restart the Tewke Tap Panel."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: TewkeCoordinator) -> None:
        """Initialise the restart button entity."""
        super().__init__(coordinator)
        config = coordinator.data["config"]
        assert config is not None
        hardware_id = config.hardware_id
        self._attr_unique_id = f"{hardware_id}_restart"

    @override
    async def async_press(self) -> None:
        """Send a restart command to the Tap Panel."""
        tap = self.coordinator.config_entry.runtime_data.tap
        try:
            await tap.restart()
        except (PyTewkeInvalidRequestError, RuntimeError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="restart_internal",
                translation_placeholders={"error": str(err)},
            ) from err
        except (
            PyTewkeCoapError,
            PyTewkeUnknownError,
            TimeoutError,
        ) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="restart_failed",
                translation_placeholders={"error": str(err)},
            ) from err
