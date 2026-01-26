"""Button support for Android TV."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Union

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AndroidTVADBRuntimeData, AndroidTVConfigEntry
from .const import CONF_CONNECTION_TYPE, CONNECTION_TYPE_REMOTE
from .entity import AndroidTVADBEntity, adb_decorator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Type alias for press actions (can be sync or async)
PressAction = Callable[["AndroidTVADBButtonEntity"], Union[None, Awaitable[None]]]


@dataclass(frozen=True, kw_only=True)
class AndroidTVButtonEntityDescription(ButtonEntityDescription):
    """Describes Android TV button entity."""

    press_action: PressAction
    is_async: bool = True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AndroidTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Android TV button entities based on a config entry."""
    connection_type = config_entry.data.get(CONF_CONNECTION_TYPE)

    # Button entities are only available for ADB connections
    # Remote protocol doesn't support ADB shell commands needed for find_remote/reboot
    if connection_type == CONNECTION_TYPE_REMOTE:
        return

    runtime_data = config_entry.runtime_data
    if not isinstance(runtime_data, AndroidTVADBRuntimeData):
        return

    entities: list[AndroidTVADBButtonEntity] = []

    for description in BUTTON_ENTITY_DESCRIPTIONS:
        entities.append(AndroidTVADBButtonEntity(config_entry, description))

    async_add_entities(entities)


async def _press_find_remote(entity: AndroidTVADBButtonEntity) -> None:
    """Press the find remote button."""
    await entity._find_remote()


async def _press_reboot(entity: AndroidTVADBButtonEntity) -> None:
    """Press the reboot button."""
    await entity._reboot()


BUTTON_ENTITY_DESCRIPTIONS: tuple[AndroidTVButtonEntityDescription, ...] = (
    AndroidTVButtonEntityDescription(
        key="find_remote",
        translation_key="find_remote",
        name="Find remote",
        icon="mdi:remote",
        press_action=_press_find_remote,
        is_async=True,
    ),
    AndroidTVButtonEntityDescription(
        key="reboot",
        translation_key="reboot",
        name="Reboot",
        icon="mdi:restart",
        press_action=_press_reboot,
        is_async=True,
    ),
)


class AndroidTVADBButtonEntity(AndroidTVADBEntity, ButtonEntity):
    """Android TV Button Entity for ADB connection."""

    entity_description: AndroidTVButtonEntityDescription

    def __init__(
        self,
        config_entry: AndroidTVConfigEntry,
        description: AndroidTVButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"
        self._attr_name = description.name

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_action(self)

    @adb_decorator()
    async def _find_remote(self) -> None:
        """Trigger the Find My Remote feature on Android TV devices."""
        # Try multiple approaches for different device types
        commands = [
            # NVIDIA Shield Remote Locator
            "am start -a android.intent.action.VIEW -n com.nvidia.remotelocator/.ShieldRemoteLocatorActivity",
            # Google TV Streamer Find Remote
            "am start -a com.google.android.tv.action.FIND_REMOTE",
            # Google TV Remote Finder Activity
            "am start -n com.google.android.katniss/.setting.FindMyRemoteActivity",
            # Broadcast intent for Google TV
            "am broadcast -a com.google.android.tv.action.FIND_REMOTE",
        ]

        for cmd in commands:
            try:
                result = await self.aftv.adb_shell(cmd)
                if result is None or (isinstance(result, str) and "Error" not in result):
                    _LOGGER.info("Find remote triggered with: %s", cmd)
                    return
            except Exception:  # noqa: BLE001
                continue

        # If none worked, try opening remote settings
        await self.aftv.adb_shell(
            "am start -a android.settings.SETTINGS -n com.android.tv.settings/.MainSettings"
        )
        _LOGGER.warning("Find remote not directly available, opened settings instead")

    @adb_decorator()
    async def _reboot(self) -> None:
        """Reboot the device."""
        await self.aftv.adb_shell("reboot")
        _LOGGER.debug("Reboot command sent")
