"""Testing for ScreenLogic diagnostics."""
from unittest.mock import DEFAULT, patch

from screenlogicpy import ScreenLogicGateway
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import (
    DATA_FULL_CHEM,
    GATEWAY_DISCOVERY_IMPORT_PATH,
    MOCK_ADAPTER_MAC,
    stub_async_connect,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    mock_config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MOCK_ADAPTER_MAC)},
    )
    with patch(
        GATEWAY_DISCOVERY_IMPORT_PATH,
        return_value={},
    ), patch.multiple(
        ScreenLogicGateway,
        async_connect=lambda *args, **kwargs: stub_async_connect(
            DATA_FULL_CHEM, *args, **kwargs
        ),
        is_connected=True,
        _async_connected_request=DEFAULT,
        get_debug=lambda self: {},
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        diag = await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        )

    assert diag == snapshot
