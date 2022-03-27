"""Test the QR Generator camera."""
from typing import Any

from homeassistant.components.camera import async_get_image
from homeassistant.components.qr_generator.const import (
    ATTR_BACKGROUND_COLOR,
    ATTR_BORDER,
    ATTR_COLOR,
    ATTR_ERROR_CORRECTION,
    ATTR_SCALE,
    ATTR_TEXT,
    CONF_ADVANCED,
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
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE, STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

DUMMY_ENTRY: dict[str, Any] = {
    CONF_NAME: "Test QR Code",
    CONF_VALUE_TEMPLATE: "Sample content",
    CONF_ADVANCED: True,
    CONF_COLOR: DEFAULT_COLOR,
    CONF_SCALE: DEFAULT_SCALE,
    CONF_BORDER: DEFAULT_BORDER,
    CONF_ERROR_CORRECTION: DEFAULT_ERROR_CORRECTION,
    CONF_BACKGROUND_COLOR: DEFAULT_BACKGROUND_COLOR,
}


async def test_camera(hass: HomeAssistant) -> None:
    """Test the creation and values of the camera."""
    config_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN, title="NINA", data=DUMMY_ENTRY
    )

    entity_registry: er = er.async_get(hass)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED

    state = hass.states.get("camera.test_qr_code")
    entry = entity_registry.async_get("camera.test_qr_code")

    assert state.state == STATE_IDLE
    assert state.attributes.get(ATTR_TEXT) == "Sample content"
    assert state.attributes.get(ATTR_COLOR) == DEFAULT_COLOR
    assert state.attributes.get(ATTR_SCALE) == DEFAULT_SCALE
    assert state.attributes.get(ATTR_BORDER) == DEFAULT_BORDER
    assert state.attributes.get(ATTR_ERROR_CORRECTION) == DEFAULT_ERROR_CORRECTION
    assert state.attributes.get(ATTR_BACKGROUND_COLOR) == DEFAULT_BACKGROUND_COLOR

    assert entry.unique_id == f"{config_entry.entry_id}-qr-code"

    image = await async_get_image(hass, "camera.test_qr_code", timeout=1)

    assert image.content
