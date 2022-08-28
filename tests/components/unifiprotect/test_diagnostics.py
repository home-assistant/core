"""Test UniFi Protect diagnostics."""

from pyunifiprotect.data import NVR, Light

from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture, init_entry

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, hass_client
):
    """Test generating diagnostics for a config entry."""

    await init_entry(hass, ufp, [light])

    diag = await get_diagnostics_for_config_entry(hass, hass_client, ufp.entry)

    nvr: NVR = ufp.api.bootstrap.nvr
    # validate some of the data
    assert "nvr" in diag and isinstance(diag["nvr"], dict)
    nvr_dict = diag["nvr"]
    # should have been anonymized
    assert nvr_dict["id"] != nvr.id
    assert nvr_dict["mac"] != nvr.mac
    assert nvr_dict["host"] != str(nvr.host)
    # should have been kept
    assert nvr_dict["firmwareVersion"] == nvr.firmware_version
    assert nvr_dict["version"] == str(nvr.version)
    assert nvr_dict["type"] == nvr.type

    assert (
        "lights" in diag
        and isinstance(diag["lights"], list)
        and len(diag["lights"]) == 1
    )
    light_dict = diag["lights"][0]
    # should have been anonymized
    assert light_dict["id"] != light.id
    assert light_dict["name"] != light.mac
    assert light_dict["mac"] != light.mac
    assert light_dict["host"] != str(light.host)
    # should have been kept
    assert light_dict["firmwareVersion"] == light.firmware_version
    assert light_dict["type"] == light.type
