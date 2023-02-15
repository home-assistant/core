"""Test the Rainforest Eagle diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.rainforest_eagle.const import (
    CONF_CLOUD_ID,
    CONF_INSTALL_CODE,
)
from homeassistant.core import HomeAssistant

from . import MOCK_200_RESPONSE_WITHOUT_PRICE

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_rainforest_200,
    config_entry_200,
) -> None:
    """Test config entry diagnostics."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry_200)

    config_entry_dict = config_entry_200.as_dict()
    config_entry_dict["data"][CONF_INSTALL_CODE] = REDACTED
    config_entry_dict["data"][CONF_CLOUD_ID] = REDACTED

    assert result == {
        "config_entry": config_entry_dict,
        "data": {
            var["Name"]: var["Value"]
            for var in MOCK_200_RESPONSE_WITHOUT_PRICE.values()
        },
    }
