"""QR Generator camera platform."""

from __future__ import annotations

import io
from typing import Any

from PIL import ImageColor
import pyqrcode

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import template
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change

from .const import (
    _LOGGER,
    ATTR_BACKGROUND_COLOR,
    ATTR_BORDER,
    ATTR_COLOR,
    ATTR_ERROR_CORRECTION,
    ATTR_SCALE,
    ATTR_TEXT,
    CONF_BACKGROUND_COLOR,
    CONF_BORDER,
    CONF_COLOR,
    CONF_ERROR_CORRECTION,
    CONF_SCALE,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_BORDER,
    DEFAULT_COLOR,
    DEFAULT_ERROR_CORRECTION,
    DEFAULT_SCALE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entries."""

    entity = QRCamera(config_entry, hass)

    async_add_entities([entity])


class QRCamera(Camera):
    """Representation of a QR code."""

    def __init__(self, entry: ConfigEntry, hass: HomeAssistant) -> None:
        """Initialize the camera."""
        super().__init__()

        self.hass: HomeAssistant = hass

        self.image: io.BytesIO = io.BytesIO()

        self.value_template: str = entry.data[CONF_VALUE_TEMPLATE]
        self.template = template.Template(self.value_template, self.hass)  # type: ignore[no-untyped-call]
        self.rendered_template: template.RenderInfo = template.RenderInfo(self.template)

        self.color_hex = entry.data.get(CONF_COLOR, DEFAULT_COLOR)
        self.color = ImageColor.getcolor(self.color_hex, "RGBA")

        self.background_color_hex = entry.data.get(
            CONF_BACKGROUND_COLOR, DEFAULT_BACKGROUND_COLOR
        )
        self.background_color = ImageColor.getcolor(self.background_color_hex, "RGBA")

        self.scale: int = entry.data.get(CONF_SCALE, DEFAULT_SCALE)
        self.border: int = entry.data.get(CONF_BORDER, DEFAULT_BORDER)
        self.error_correction: str = entry.data.get(
            CONF_ERROR_CORRECTION, DEFAULT_ERROR_CORRECTION
        )

        self._attr_name: str = entry.data[CONF_NAME]
        self._attr_unique_id: str = f"{entry.entry_id}-qr-code"

    def _render(self) -> None:
        """Render template."""
        self.rendered_template = self.template.async_render_to_info()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        self._render()
        self._refresh()

        @callback
        def _update(entity: Any, old_state: Any, new_state: Any) -> None:
            """Handle state changes."""
            if old_state is None or new_state is None:
                return

            if old_state.state == new_state.state:
                return

            self._render()
            self._refresh()

        async_track_state_change(
            self.hass, list(self.rendered_template.entities), _update
        )

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        return self.image.getvalue()

    def _refresh(self) -> None:
        """Create the QR code."""
        _LOGGER.debug('Print "%s" with: %s', self.name, self.rendered_template.result())

        code = pyqrcode.create(
            self.rendered_template.result(), error=self.error_correction
        )

        self.image = io.BytesIO()
        code.png(
            self.image,
            scale=self.scale,
            module_color=self.color,
            background=self.background_color,
            quiet_zone=self.border,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes of the sensor."""
        return {
            ATTR_TEXT: self.rendered_template.result(),
            ATTR_COLOR: self.color_hex,
            ATTR_BACKGROUND_COLOR: self.background_color_hex,
            ATTR_SCALE: self.scale,
            ATTR_BORDER: self.border,
            ATTR_ERROR_CORRECTION: self.error_correction,
        }
