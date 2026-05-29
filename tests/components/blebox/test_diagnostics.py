"""Tests for BleBox diagnostics."""

from unittest.mock import AsyncMock, PropertyMock, create_autospec, patch

import blebox_uniapi.box
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.blebox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.fixture(name="product_mock")
def product_mock_fixture() -> blebox_uniapi.box.Box:
    """Return a product mock for diagnostics testing."""
    product = create_autospec(blebox_uniapi.box.Box, instance=True)
    type(product).features = PropertyMock(return_value={})
    type(product).name = PropertyMock(return_value="My Device")
    type(product).type = PropertyMock(return_value="switchBox")
    type(product).model = PropertyMock(return_value="BleBox switchBox")
    type(product).unique_id = PropertyMock(return_value="aabbccddeeff")
    type(product).firmware_version = PropertyMock(return_value="1.0.0")
    type(product).hardware_version = PropertyMock(return_value="0.1")
    type(product).available_firmware_version = PropertyMock(return_value="1.0.1")
    type(product).api_version = PropertyMock(return_value=20200229)
    type(product).last_data = PropertyMock(return_value={"relay": [{"state": 0}]})
    return product


@pytest.mark.parametrize(
    "entry_data",
    [
        pytest.param(
            {CONF_HOST: "172.100.123.4", CONF_PORT: 80},
            id="no_credentials",
        ),
        pytest.param(
            {
                CONF_HOST: "172.100.123.4",
                CONF_PORT: 80,
                CONF_USERNAME: "user",
                CONF_PASSWORD: "secret",
            },
            id="with_credentials",
        ),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    product_mock: blebox_uniapi.box.Box,
    snapshot: SnapshotAssertion,
    entry_data: dict,
) -> None:
    """Test diagnostics output, including credential redaction."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    with patch.object(
        blebox_uniapi.box.Box,
        "async_from_host",
        AsyncMock(return_value=product_mock),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot(
        exclude=props("entry_id", "created_at", "modified_at")
    )
