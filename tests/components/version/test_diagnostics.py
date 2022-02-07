"""Test version diagnostics."""


from aioaseko import ClientSession

from homeassistant.core import HomeAssistant

from .common import MOCK_VERSION, setup_version_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_version_sensor(
    hass: HomeAssistant,
    hass_client: ClientSession,
):
    """Test diagnostic information."""
    config_entry = await setup_version_integration(hass)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    print(diagnostics)
    assert diagnostics["entry"]["data"] == {
        "name": "",
        "channel": "stable",
        "image": "default",
        "board": "OVA",
        "version_source": "Local installation",
        "source": "local",
    }

    assert diagnostics["coordinator_data"] == {
        "version": MOCK_VERSION,
        "version_data": None,
    }
    assert len(diagnostics["devices"]) == 1
