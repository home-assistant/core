"""Common fixtures for the Tween Light Infrared tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tween_light_ir.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
)

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tween_light_ir.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="LED Strip",
        entry_id="1234567890",
        data={
            CONF_DEVICE_TYPE: "led_strip",
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
        },
    )


@pytest.fixture(name="led_strip_codes")
def mock_tween_light_led_strip_code_to_command() -> Generator[None]:
    """Patch TweenLightLEDStripCode.to_command to return the TweenLightLEDStripCode directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw NEC timings.
    """
    with patch(
        "infrared_protocols.codes.tween_light.led_strip.TweenLightLEDStripCode.to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ):
        yield
