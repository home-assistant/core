"""Test UniFi Protect diagnostics."""

from pyunifiprotect.data import NVR, Light

from homeassistant.core import HomeAssistant

from .conftest import MockEntityFixture, regenerate_device_ids

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light, hass_client
):
    """Test generating diagnostics for a config entry."""

    light1 = mock_light.copy()
    light1._api = mock_entry.api
    light1.name = "Test Light 1"
    regenerate_device_ids(light1)

    mock_entry.api.bootstrap.lights = {
        light1.id: light1,
    }
    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry.entry)

    nvr_obj: NVR = mock_entry.api.bootstrap.nvr
    # validate some of the data
    assert "nvr" in diag and isinstance(diag["nvr"], dict)
    nvr = diag["nvr"]
    # should have been anonymized
    assert nvr["id"] != nvr_obj.id
    assert nvr["mac"] != nvr_obj.mac
    assert nvr["host"] != str(nvr_obj.host)
    # should have been kept
    assert nvr["firmwareVersion"] == nvr_obj.firmware_version
    assert nvr["version"] == str(nvr_obj.version)
    assert nvr["type"] == nvr_obj.type

    assert (
        "lights" in diag
        and isinstance(diag["lights"], list)
        and len(diag["lights"]) == 1
    )
    light = diag["lights"][0]
    # should have been anonymized
    assert light["id"] != light1.id
    assert light["name"] != light1.mac
    assert light["mac"] != light1.mac
    assert light["host"] != str(light1.host)
    # should have been kept
    assert light["firmwareVersion"] == light1.firmware_version
    assert light["type"] == light1.type
