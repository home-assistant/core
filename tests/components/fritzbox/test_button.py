"""Tests for AVM Fritz!Box templates."""

from datetime import timedelta
from unittest.mock import Mock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_DEVICES, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import FritzEntityBaseMock, set_devices, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed, snapshot_platform

ENTITY_ID = f"{BUTTON_DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
) -> None:
    """Test if is initialized correctly."""
    template = FritzEntityBaseMock()
    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.BUTTON]):
        entry = await setup_config_entry(
            hass,
            MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0],
            fritz=fritz,
            template=template,
        )
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_apply_template(hass: HomeAssistant, fritz: Mock) -> None:
    """Test if applies works."""
    template = FritzEntityBaseMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], fritz=fritz, template=template
    )

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert fritz().apply_template.call_count == 1


async def test_discover_new_device(hass: HomeAssistant, fritz: Mock) -> None:
    """Test adding new discovered devices during runtime."""
    template = FritzEntityBaseMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], fritz=fritz, template=template
    )

    state = hass.states.get(ENTITY_ID)
    assert state

    new_template = FritzEntityBaseMock()
    new_template.ain = "7890 1234"
    new_template.name = "new_template"
    set_devices(fritz, templates=[template, new_template])

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{BUTTON_DOMAIN}.new_template")
    assert state
