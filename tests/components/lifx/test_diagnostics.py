"""Test LIFX diagnostics."""

from collections.abc import Callable

from lifx import Device
import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import async_setup_lifx_entry
from .helpers import (
    create_reference_brightness_light,
    create_reference_ceiling_128_light,
    create_reference_ceiling_light,
    create_reference_color_light,
    create_reference_color_temperature_light,
    create_reference_extended_multizone_light,
    create_reference_hev_light,
    create_reference_infrared_light,
    create_reference_legacy_multizone_light,
    create_reference_matrix_light,
    create_reference_thread_light,
)


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(create_reference_color_light, id="color"),
        pytest.param(create_reference_color_temperature_light, id="color_temperature"),
        pytest.param(create_reference_brightness_light, id="brightness"),
        pytest.param(create_reference_infrared_light, id="infrared"),
        pytest.param(create_reference_hev_light, id="hev"),
        pytest.param(create_reference_legacy_multizone_light, id="legacy_multizone"),
        pytest.param(
            create_reference_extended_multizone_light, id="extended_multizone"
        ),
        pytest.param(create_reference_matrix_light, id="matrix"),
        pytest.param(create_reference_ceiling_light, id="ceiling"),
        pytest.param(create_reference_ceiling_128_light, id="ceiling_128"),
        pytest.param(create_reference_thread_light, id="thread"),
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
