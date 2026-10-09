"""Tests for the Vistapool button platform."""

from collections.abc import Generator
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

from aioaquarite import AquariteError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.vistapool.button import _LED_PULSE_DELAY_SECONDS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

_BUTTON = "button.my_pool_led_next_color"
_LED_DATA = {"main": {"hasLED": 1, "version": 1}, "light": {"status": 0}}


@pytest.fixture(autouse=True)
def _only_button_platform() -> Generator[None]:
    """Restrict integration setup to the button platform for these tests."""
    with patch("homeassistant.components.vistapool.PLATFORMS", [Platform.BUTTON]):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the LED-pulse button when hasLED is set."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LED_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_button_not_created_without_led(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test the LED-pulse button is not created when hasLED is 0."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(_BUTTON) is None


async def test_button_press_when_light_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test pressing the button when the light is off just turns it on."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LED_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _BUTTON},
        blocking=True,
    )

    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", "light.status", 1
    )


async def test_button_press_when_light_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test pressing the button when the light is on runs the library pulse."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasLED": 1, "version": 1},
        "light": {"status": 1},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _BUTTON},
        blocking=True,
    )

    mock_vistapool_client.pulse.assert_awaited_once_with(
        "ABCDEF1234567890", "light.status", 0, 1, _LED_PULSE_DELAY_SECONDS
    )
    mock_vistapool_client.set_value.assert_not_awaited()


async def test_button_press_rapid_repeat_after_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a second press lands the pulse instead of repeating turn-on.

    The library delivers the acknowledged turn-on through the data callback
    before the Firestore push round-trips, so the second press reads the
    light as on and pulses it instead of sending another bare on.
    """
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LED_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _BUTTON},
        blocking=True,
    )
    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", "light.status", 1
    )

    on_data({"main": {"hasLED": 1, "version": 1}, "light": {"status": 1}})
    await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _BUTTON},
        blocking=True,
    )

    mock_vistapool_client.pulse.assert_awaited_once_with(
        "ABCDEF1234567890", "light.status", 0, 1, _LED_PULSE_DELAY_SECONDS
    )
    assert mock_vistapool_client.set_value.await_count == 1


@pytest.mark.parametrize(
    ("light_status", "failing_method"),
    [
        pytest.param(0, "set_value", id="turn_on_fails"),
        pytest.param(1, "pulse", id="pulse_fails"),
    ],
)
async def test_button_press_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    light_status: int,
    failing_method: str,
) -> None:
    """Test the button re-raises HomeAssistantError when the library fails."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasLED": 1, "version": 1},
        "light": {"status": light_status},
    }
    getattr(mock_vistapool_client, failing_method).side_effect = AquariteError("boom")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: _BUTTON},
            blocking=True,
        )
    assert excinfo.value.translation_key == "set_failed"
