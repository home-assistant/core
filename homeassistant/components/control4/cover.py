"""Platform for Control4 Covers (blinds/shades and garage doors)."""

from collections.abc import Callable
import logging
from typing import Any

from pyControl4.blind import C4Blind

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Control4Entity
from .const import (
    CONF_DIRECTOR,
    CONF_DIRECTOR_ALL_ITEMS,
    CONTROL4_ENTITY_TYPE,
    Control4ConfigEntry,
)
from .director_utils import director_get_entry_variables

_LOGGER = logging.getLogger(__name__)

# Substrings commonly found in Control4 proxy identifiers for window coverings
_COVER_PROXY_SUBSTRINGS = (
    "shade",
    "blind",
    "windowcover",
    "curtain",
    "drap",
)

_DEFAULT_SUPPORTED_FEATURES = (
    CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
)

_MIN_COVER_LEVEL = 0
_MAX_COVER_LEVEL = 100


class Control4CoverModel:
    """Encapsulates device-class and state-accessor logic for a specific cover model."""

    def __init__(
        self,
        cover_device_class: CoverDeviceClass | None = None,
        is_stateful: bool = False,
        fn_get_position: Callable[[dict[str, Any]], Any] | None = None,
        fn_is_closed: Callable[[dict[str, Any]], bool | None] | None = None,
        fn_is_closing: Callable[[dict[str, Any]], bool | None] | None = None,
        fn_is_opening: Callable[[dict[str, Any]], bool | None] | None = None,
        supported_features: CoverEntityFeature = _DEFAULT_SUPPORTED_FEATURES,
    ) -> None:
        """Initialize the cover model descriptor."""
        self.cover_device_class = cover_device_class
        self.is_stateful = bool(is_stateful)
        self.fn_get_position = fn_get_position
        self.fn_is_closed = fn_is_closed
        self.fn_is_closing = fn_is_closing
        self.fn_is_opening = fn_is_opening
        self.supported_features = supported_features

    def is_positional(self) -> bool:
        """Return True if the cover supports SET_POSITION."""
        return bool(self.supported_features & CoverEntityFeature.SET_POSITION)

    def is_gate(self) -> bool:
        """Return True if the cover device class is GATE."""
        return self.cover_device_class == CoverDeviceClass.GATE

    def get_position(self, attributes: dict[str, Any]) -> Any:
        """Return the current position from attributes, or None."""
        if self.fn_get_position is not None:
            return self.fn_get_position(attributes)
        return None

    def get_is_closed(self, attributes: dict[str, Any]) -> bool | None:
        """Return whether the cover is closed, or None if unknown."""
        if self.fn_is_closed is not None:
            return self.fn_is_closed(attributes)
        return None

    def get_is_closing(self, attributes: dict[str, Any]) -> bool | None:
        """Return whether the cover is closing, or None if unknown."""
        if self.fn_is_closing is not None:
            return self.fn_is_closing(attributes)
        return None

    def get_is_opening(self, attributes: dict[str, Any]) -> bool | None:
        """Return whether the cover is opening, or None if unknown."""
        if self.fn_is_opening is not None:
            return self.fn_is_opening(attributes)
        return None


# Known driver filenames mapped to their model descriptors.
_KNOWN_COVER_MODELS: dict[str, Control4CoverModel] = {
    "blind_qmotion_qadvanced_roller_shade.c4z": Control4CoverModel(
        cover_device_class=CoverDeviceClass.SHADE,
        is_stateful=True,
        fn_get_position=lambda attr: attr.get("Level"),
        fn_is_closed=lambda attr: attr.get("Fully Closed"),
        fn_is_closing=lambda attr: attr.get("Closing"),
        fn_is_opening=lambda attr: attr.get("Opening"),
        supported_features=_DEFAULT_SUPPORTED_FEATURES
        | CoverEntityFeature.SET_POSITION,
    ),
    "gate_relay_control.c4z": Control4CoverModel(
        cover_device_class=CoverDeviceClass.GATE,
        is_stateful=True,
        fn_is_closed=lambda attr: attr.get("STATE") == "Closed",
    ),
}

_DEFAULT_COVER_MODEL = Control4CoverModel()

# Garage door detection constants (uibutton relay driver)
_GARAGE_PARENT_TYPE = 6
_GARAGE_PROXY = "uibutton"
_GARAGE_PARENT_NAME = "relay garage door controller"
_GARAGE_PARENT_MODEL = "1-3 relays"
_GARAGE_STATE_VARIABLE = "STATE"
_GARAGE_ICON_VARIABLE = "ICON"
_GARAGE_ICON_DESCRIPTION_VARIABLE = "ICON_DESCRIPTION"
_GARAGE_REFRESH_DELAYS = (5, 10, 20, 35, 60)
_GARAGE_TRANSITION_TIMEOUT = 45


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control4 covers from a config entry."""
    entry_data = entry.runtime_data
    all_items: list[dict[str, Any]] = entry_data[CONF_DIRECTOR_ALL_ITEMS]

    items_by_id = {item.get("id"): item for item in all_items if "id" in item}

    def _is_cover_proxy(proxy_value: str | None) -> bool:
        if not proxy_value or not isinstance(proxy_value, str):
            return False
        p = proxy_value.lower()
        return any(s in p for s in _COVER_PROXY_SUBSTRINGS)

    def _get_cover_model(item: dict[str, Any]) -> Control4CoverModel | None:
        cover_model = _KNOWN_COVER_MODELS.get(item.get("protocolFilename", ""))
        if cover_model is not None:
            return cover_model
        if _is_cover_proxy(item.get("proxy")):
            return _DEFAULT_COVER_MODEL
        return None

    def _is_garage_parent(item: dict[str, Any]) -> bool:
        name = str(item.get("name", "")).lower()
        model = str(item.get("model", "")).lower()
        return (
            item.get("type") == _GARAGE_PARENT_TYPE
            and item.get("proxy") == _GARAGE_PROXY
            and _GARAGE_PARENT_NAME in name
            and _GARAGE_PARENT_MODEL in model
        )

    garage_parent_ids = {
        item["id"] for item in all_items if item.get("id") and _is_garage_parent(item)
    }

    garage_items: list[dict[str, Any]] = [
        item
        for item in all_items
        if item.get("type") == CONTROL4_ENTITY_TYPE
        and item.get("id")
        and item.get("proxy") == _GARAGE_PROXY
        and item.get("parentId") in garage_parent_ids
    ]

    entity_list: list[CoverEntity] = []

    for item in all_items:
        if item.get("type") != CONTROL4_ENTITY_TYPE or not item.get("id"):
            continue

        cover_model = _get_cover_model(item)
        if cover_model is None:
            continue

        try:
            item_name = str(item["name"])
            item_id = item["id"]
            item_area = item.get("roomName")
            item_parent_id = item["parentId"]

            item_manufacturer = None
            item_device_name = None
            item_model = None

            parent = items_by_id.get(item_parent_id)
            if parent:
                item_manufacturer = parent.get("manufacturer")
                item_device_name = parent.get("name")
                item_model = parent.get("model")
        except KeyError:
            _LOGGER.exception(
                "Unknown device properties received from Control4: %s",
                item,
            )
            continue

        item_attributes = await director_get_entry_variables(hass, entry, item_id)
        if item_attributes is None:
            _LOGGER.debug("Skipping cover %s: no initial variables", item_name)
            continue

        entity_list.append(
            Control4Cover(
                cover_model,
                entry_data,
                entry,
                item_name,
                item_id,
                item_device_name,
                item_manufacturer,
                item_model,
                item_parent_id,
                item_area,
                item_attributes,
            )
        )

    for item in garage_items:
        try:
            item_name = str(item["name"])
            item_id = item["id"]
            item_area = item.get("roomName")
            item_parent_id = item["parentId"]

            parent = items_by_id.get(item_parent_id, {})
            item_manufacturer = parent.get("manufacturer")
            item_device_name = item_name
            item_model = parent.get("model")
        except KeyError:
            _LOGGER.exception(
                "Unknown garage door properties received from Control4: %s",
                item,
            )
            continue

        item_attributes = await director_get_entry_variables(hass, entry, item_id)
        if _GARAGE_STATE_VARIABLE not in item_attributes:
            item_attributes.update(
                await director_get_entry_variables(hass, entry, item_parent_id)
            )

        entity_list.append(
            Control4GarageCover(
                entry_data,
                entry,
                item_name,
                item_id,
                item_device_name,
                item_manufacturer,
                item_model,
                item_parent_id,
                item_area,
                item_attributes,
            )
        )

    async_add_entities(entity_list, True)


class Control4Cover(Control4Entity, CoverEntity):  # type: ignore[misc]
    """Control4 cover (blinds/shades) entity."""

    _attr_translation_key = "blind"

    def __init__(
        self,
        cover_model: Control4CoverModel,
        entry_data: dict[str, Any],
        entry: Control4ConfigEntry,
        name: str,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
        device_area: str | None,
        device_attributes: dict[str, Any],
    ) -> None:
        """Initialize Control4 cover entity."""
        super().__init__(
            entry_data,
            entry,
            name,
            idx,
            device_name,
            device_manufacturer,
            device_model,
            device_id,
            device_area,
            device_attributes,
        )
        self._cover_model = cover_model
        self._attr_device_class = cover_model.cover_device_class
        self._attr_supported_features = cover_model.supported_features

    def _create_blind_api_object(self) -> C4Blind:
        """Create a pyControl4 blind object with the current director token."""
        return C4Blind(self.entry_data[CONF_DIRECTOR], self._idx)

    @property
    def current_cover_position(self) -> int | None:  # type: ignore[override]
        """Return current cover position (0-100)."""
        if not self._cover_model.is_stateful:
            return None
        p = self._cover_model.get_position(self._extra_state_attributes)
        if isinstance(p, str) and p.isdigit():
            p = int(p)
        if isinstance(p, int) and _MIN_COVER_LEVEL <= p <= _MAX_COVER_LEVEL:
            return p
        return None

    @property
    def is_closed(self) -> bool | None:  # type: ignore[override]
        """Return whether cover is closed."""
        if not self._cover_model.is_stateful:
            return None
        closed = self._cover_model.get_is_closed(self._extra_state_attributes)
        if closed is not None:
            return closed
        pos = self.current_cover_position
        if pos is not None:
            return pos == 0
        return None

    @property
    def is_closing(self) -> bool | None:  # type: ignore[override]
        """Return whether cover is closing."""
        if not self._cover_model.is_stateful:
            return None
        return self._cover_model.get_is_closing(self._extra_state_attributes)

    @property
    def is_opening(self) -> bool | None:  # type: ignore[override]
        """Return whether cover is opening."""
        if not self._cover_model.is_stateful:
            return None
        return self._cover_model.get_is_opening(self._extra_state_attributes)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._create_blind_api_object().open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._create_blind_api_object().close()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._create_blind_api_object().stop()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        if not self._cover_model.is_positional():
            return
        p = kwargs.get(ATTR_POSITION)
        if not isinstance(p, int):
            return
        p = max(_MIN_COVER_LEVEL, min(p, _MAX_COVER_LEVEL))
        await self._create_blind_api_object().set_level_target(level=p)


class Control4GarageCover(Control4Entity, CoverEntity):  # type: ignore[misc]
    """Control4 garage door cover entity."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    @property
    def is_closed(self) -> bool | None:  # type: ignore[override]
        """Return whether the garage door is closed."""
        state = str(
            self._extra_state_attributes.get(_GARAGE_STATE_VARIABLE, "")
        ).lower()
        if state in {"closed", "close"}:
            return True
        if state in {"open", "opened", "opening", "closing"}:
            return False
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door."""
        await self.entry_data[CONF_DIRECTOR].send_post_request(
            f"/api/v1/items/{self._device_id}/commands", "OPEN", {}
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door."""
        await self.entry_data[CONF_DIRECTOR].send_post_request(
            f"/api/v1/items/{self._device_id}/commands", "CLOSE", {}
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the garage door."""
        await self.entry_data[CONF_DIRECTOR].send_post_request(
            f"/api/v1/items/{self._device_id}/commands", "STOP", {}
        )
