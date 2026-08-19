"""Tests for the xiaomi_miio services."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.xiaomi_miio.const import (
    CONF_FLOW_TYPE,
    DOMAIN,
    SERVICE_EYECARE_MODE_ON,
    SERVICE_SET_SCENE,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import Context, HomeAssistant

from . import TEST_MAC

from tests.common import MockConfigEntry

CEILING_MODEL = "philips.light.ceiling"
EYECARE_MODEL = "philips.light.sread1"
CEILING_ENTITY_ID = "light.test_light"
EYECARE_ENTITY_ID = "light.test_light_eyecare"


@pytest.fixture(name="mock_light")
def mock_light_fixture() -> Generator[MagicMock]:
    """Mock the light device."""
    status = Mock(
        is_on=True,
        brightness=50,
        color_temperature=50,
        scene=1,
        delay_off_countdown=0,
        smart_night_light=False,
        eyecare=False,
        reminder=False,
        ambient=False,
        ambient_brightness=0,
    )
    mock_light = MagicMock()
    mock_light.status = Mock(return_value=status)
    # The entity is polled again after the service call, so let the mocked
    # device apply the change to make the resulting state write observable
    mock_light.set_scene = Mock(
        side_effect=lambda scene: setattr(status, "scene", scene)
    )
    mock_light.eyecare_on = Mock(side_effect=lambda: setattr(status, "eyecare", True))

    with (
        patch(
            "homeassistant.components.xiaomi_miio.get_platforms",
            return_value=[Platform.LIGHT],
        ),
        patch(
            "homeassistant.components.xiaomi_miio.light.Ceil", return_value=mock_light
        ),
        patch(
            "homeassistant.components.xiaomi_miio.light.PhilipsEyecare",
            return_value=mock_light,
        ),
    ):
        yield mock_light


async def setup_light(hass: HomeAssistant, model: str, title: str) -> MockConfigEntry:
    """Set up a xiaomi_miio light."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"123456-{model}",
        title=title,
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: model,
            CONF_MAC: TEST_MAC,
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.mark.usefixtures("mock_light")
async def test_entity_service_forwards_context(
    hass: HomeAssistant, mock_light: MagicMock
) -> None:
    """Test a service using the entity service helper attributes the caller."""
    await setup_light(hass, CEILING_MODEL, "Test Light")

    context = Context()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SCENE,
        {"entity_id": CEILING_ENTITY_ID, "scene": 2},
        blocking=True,
        context=context,
    )

    mock_light.set_scene.assert_called_once_with(2)
    state = hass.states.get(CEILING_ENTITY_ID)
    assert state.attributes["scene"] == 2
    assert state.context is context


@pytest.mark.usefixtures("mock_light")
async def test_legacy_service_forwards_context(
    hass: HomeAssistant, mock_light: MagicMock
) -> None:
    """Test a service kept in-line attributes the caller.

    These services cannot use the entity service helper because the entities
    sharing the data key only partially implement the methods.
    """
    await setup_light(hass, EYECARE_MODEL, "Test Light Eyecare")

    context = Context()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EYECARE_MODE_ON,
        {"entity_id": EYECARE_ENTITY_ID},
        blocking=True,
        context=context,
    )

    mock_light.eyecare_on.assert_called_once_with()
    state = hass.states.get(EYECARE_ENTITY_ID)
    assert state.attributes["eyecare_mode"] is True
    assert state.context is context
