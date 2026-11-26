"""Test LIFX diagnostics."""

from collections.abc import Callable

from lifx import Device
import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import async_setup_lifx_entry
from .helpers import create_mock_light, create_mock_thread_light


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(create_mock_light, id="color"),
        # Thread is the only state that carries a network name to redact
        pytest.param(create_mock_thread_light, id="thread"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    factory: Callable[[], Device],
) -> None:
    """Test public typed diagnostics and private-value redaction."""
    entry = await async_setup_lifx_entry(hass, factory())

    hass.config_entries.async_update_entry(entry, title="Private bedroom light")

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["entry"]["title"] == "**REDACTED**"
    assert diagnostics == snapshot
