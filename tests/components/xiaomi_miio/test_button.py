"""The tests for the xiaomi_miio button component."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.xiaomi_miio.const import (
    CONF_FLOW_TYPE,
    DOMAIN as XIAOMI_DOMAIN,
    MODELS_VACUUM,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import TEST_MAC

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def setup_test(hass: HomeAssistant):
    """Initialize test xiaomi_miio for button entity."""

    mock_vacuum = MagicMock()

    with (
        patch(
            "homeassistant.components.xiaomi_miio.get_platforms",
            return_value=[
                Platform.BUTTON,
            ],
        ),
        patch("homeassistant.components.xiaomi_miio.RoborockVacuum") as mock_vacuum_cls,
    ):
        mock_vacuum_cls.return_value = mock_vacuum
        yield mock_vacuum


async def test_vacuum_button_params(hass: HomeAssistant) -> None:
    """Test the initial parameters of a vacuum button."""

    entity_id = await setup_component(hass, "test_vacuum")

    state = hass.states.get(f"{entity_id}_reset_main_brush")
    assert state
    assert state.state == "unknown"


@pytest.mark.freeze_time("2023-06-28 00:00:00+00:00")
async def test_vacuum_button_press(hass: HomeAssistant) -> None:
    """Test pressing a vacuum button."""

    entity_id = await setup_component(hass, "test_vacuum")

    state = hass.states.get(f"{entity_id}_reset_side_brush")
    assert state
    assert state.state == "unknown"

    pressed_at = dt_util.utcnow()
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id + "_reset_side_brush"},
        blocking=True,
    )

    state = hass.states.get(f"{entity_id}_reset_side_brush")
    assert state
    assert state.state == pressed_at.isoformat()


async def setup_component(hass: HomeAssistant, entity_name: str) -> str:
    """Set up vacuum component."""
    entity_id = f"{BUTTON_DOMAIN}.{entity_name}"

    config_entry = MockConfigEntry(
        domain=XIAOMI_DOMAIN,
        unique_id="123456",
        title=entity_name,
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: MODELS_VACUUM[0],
            CONF_MAC: TEST_MAC,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return entity_id
