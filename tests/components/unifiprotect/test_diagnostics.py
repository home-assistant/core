"""Test UniFi Protect diagnostics."""
from pyunifiprotect.data import NVR, Light

from homeassistant.components.unifiprotect.const import CONF_ALLOW_EA
from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture, init_entry

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test generating diagnostics for a config entry."""

    await init_entry(hass, ufp, [light])

    options = dict(ufp.entry.options)
    options[CONF_ALLOW_EA] = True
    hass.config_entries.async_update_entry(ufp.entry, options=options)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, ufp.entry)

    assert "options" in diag and isinstance(diag["options"], dict)
    options = diag["options"]
    assert options[CONF_ALLOW_EA] is True

    assert "bootstrap" in diag and isinstance(diag["bootstrap"], dict)
    bootstrap = diag["bootstrap"]
    nvr: NVR = ufp.api.bootstrap.nvr
    # validate some of the data
    assert "nvr" in bootstrap and isinstance(bootstrap["nvr"], dict)
    nvr_dict = bootstrap["nvr"]
    # should have been anonymized
    assert nvr_dict["id"] != nvr.id
    assert nvr_dict["mac"] != nvr.mac
    assert nvr_dict["host"] != str(nvr.host)
    # should have been kept
    assert nvr_dict["firmwareVersion"] == nvr.firmware_version
    assert nvr_dict["version"] == str(nvr.version)
    assert nvr_dict["type"] == nvr.type

    assert (
        "lights" in bootstrap
        and isinstance(bootstrap["lights"], list)
        and len(bootstrap["lights"]) == 1
    )
    light_dict = bootstrap["lights"][0]
    # should have been anonymized
    assert light_dict["id"] != light.id
    assert light_dict["name"] != light.mac
    assert light_dict["mac"] != light.mac
    assert light_dict["host"] != str(light.host)
    # should have been kept
    assert light_dict["firmwareVersion"] == light.firmware_version
    assert light_dict["type"] == light.type
