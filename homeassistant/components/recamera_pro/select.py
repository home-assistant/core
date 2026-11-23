"""Video resolution settings on the dedicated video device."""

from dataclasses import dataclass
from typing import Any

from recamera_protocol import RecameraError, supported_resolutions

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntryHider

from .const import DOMAIN
from .coordinator import RecameraCoordinator
from .entity import RecameraEntity, recamera_picture_device_info, recamera_service_error

PARALLEL_UPDATES = 0

RESOLUTION_OPTIONS = {
    "main": list(supported_resolutions(0)),
    "sub": list(supported_resolutions(1)),
}


@dataclass(frozen=True, kw_only=True)
class VideoSelectDescription(SelectEntityDescription):
    """Description for one video select entity."""

    stream: str
    key: str
    field: str
    argument: str
    options: list[str]


VIDEO_DESCRIPTIONS = (
    *tuple(
        VideoSelectDescription(
            stream=stream,
            key=f"{stream}_resolution",
            field="sResolution",
            argument="resolution",
            options=RESOLUTION_OPTIONS[stream],
        )
        for stream in ("main", "sub")
    ),
    *tuple(
        VideoSelectDescription(
            stream=stream,
            key=f"{stream}_encoding",
            field="sOutputDataType",
            argument="codec",
            options=["H.264", "H.265"],
        )
        for stream in ("main", "sub")
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up stream resolution selectors."""
    coordinator: RecameraCoordinator = config_entry.runtime_data
    created: set[str] = set()

    def add_supported_entities() -> None:
        descriptions = [
            description
            for description in VIDEO_DESCRIPTIONS
            if description.key not in created
            and _select_is_supported(coordinator, description)
        ]
        if not descriptions:
            return
        created.update(description.key for description in descriptions)
        async_add_entities(
            [
                RecameraVideoSelect(coordinator, description)
                for description in descriptions
            ]
        )
        _sync_select_visibility(hass, coordinator)

    add_supported_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(add_supported_entities))
    _sync_select_visibility(hass, coordinator)


def _select_is_supported(
    coordinator: RecameraCoordinator,
    description: VideoSelectDescription,
) -> bool:
    """Return whether the device currently exposes the selected field."""
    data = getattr(coordinator, "data", None)
    media_profiles = getattr(data, "media_profiles", {})
    encode = media_profiles.get(description.stream, {}).get("encode") or {}
    return str(encode.get(description.field) or "") in description.options


def _select_visibility_is_supported(
    coordinator: RecameraCoordinator,
    description: VideoSelectDescription,
) -> bool:
    """Keep existing controls visible while capability data is temporarily absent."""
    if getattr(coordinator, "data", None) is None:
        return True
    return _select_is_supported(coordinator, description)


class RecameraVideoSelect(RecameraEntity, SelectEntity):
    """Expose one writable video encoding field."""

    entity_description: VideoSelectDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: RecameraCoordinator,
        description: VideoSelectDescription,
    ) -> None:
        """Initialize one video select entity."""
        super().__init__(coordinator)
        self._attr_device_info = recamera_picture_device_info(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_options = description.options
        self._attr_unique_id = f"{coordinator.device_id}_video_{description.key}"
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    @property
    def _encode(self) -> dict[str, Any]:
        """Return the current stream encoding configuration."""
        profile = (
            self.coordinator.data.media_profiles.get(self.entity_description.stream)
            or {}
        )
        encode = profile.get("encode")
        return dict(encode) if isinstance(encode, dict) else {}

    @property
    def available(self) -> bool:
        """Require current encoding metadata for writable controls."""
        return super().available and self.current_option is not None

    @property
    def current_option(self) -> str | None:
        """Return the current device value."""
        value = str(self._encode.get(self.entity_description.field) or "")
        return value if value in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Write one supported encoding option to the device."""
        try:
            if self.entity_description.argument == "resolution":
                await self.coordinator.async_update_video_encode(
                    self.entity_description.stream, resolution=option
                )
        except RecameraError as err:
            raise recamera_service_error(err) from err


def _sync_select_visibility(
    hass: HomeAssistant,
    coordinator: RecameraCoordinator,
) -> None:
    """Unhide current picture selects and hide obsolete registry entries."""
    registry = er.async_get(hass)
    kept = {
        f"{coordinator.device_id}_video_{description.key}"
        for description in VIDEO_DESCRIPTIONS
        if _select_visibility_is_supported(coordinator, description)
    }
    for entry in list(registry.entities.values()):
        if (
            entry.platform != DOMAIN
            or entry.config_entry_id != coordinator.config_entry.entry_id
            or not str(entry.entity_id).startswith("select.")
            or entry.hidden_by == RegistryEntryHider.USER
        ):
            continue
        desired_hidden = (
            None if entry.unique_id in kept else RegistryEntryHider.INTEGRATION
        )
        if entry.hidden_by != desired_hidden:
            registry.async_update_entity(
                entry.entity_id,
                hidden_by=desired_hidden,
            )
