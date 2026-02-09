"""Define tests for Lunatone diagnostics."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from . import BASE_URL, DEVICE_DATA_LIST, INFO_DATA, setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry level diagnostics."""
    await setup_integration(hass, mock_config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics == {
        "entry_data": {"url": BASE_URL},
        "data": {
            "info": INFO_DATA.model_dump(),
            "devices": [d.model_dump() for d in DEVICE_DATA_LIST],
        },
    }
