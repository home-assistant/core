"""Test LIFX diagnostics."""

from collections.abc import Callable

from lifx import Connectivity, Device, ThreadInfo, ThreadRoutingRole
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import async_setup_lifx_entry
from .helpers import (
    create_mock_light,
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
)

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


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


async def test_thread_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the Thread network name is redacted from radio diagnostics."""
    device = create_mock_light()
    device.connectivity = Connectivity.THREAD
    device.state.thread_info = ThreadInfo(
        rloc=1024,
        network_name="Private mesh",
        role=ThreadRoutingRole.ROUTER,
        next_hop=2048,
        link_quality_in=3,
        link_quality_out=3,
        link_margin_db=40,
    )
    entry = await async_setup_lifx_entry(hass, device)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["data"]["thread_info"]["network_name"] == "**REDACTED**"
    assert diagnostics["data"]["thread_info"]["rssi"] == -60
