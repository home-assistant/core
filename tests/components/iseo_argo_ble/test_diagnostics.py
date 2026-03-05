"""Test the ISEO Argo BLE diagnostics platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.iseo_argo_ble.const import (
    CONF_ADDRESS,
    CONF_PRIV_SCALAR,
    CONF_UUID,
)
from homeassistant.core import HomeAssistant

from . import MOCK_ADDRESS

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert diag["config_entry_data"][CONF_ADDRESS] == MOCK_ADDRESS
    assert diag["config_entry_data"][CONF_UUID] == "**REDACTED**"
    assert diag["config_entry_data"][CONF_PRIV_SCALAR] == "**REDACTED**"
