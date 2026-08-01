"""BleBox devices setup tests."""

import blebox_uniapi
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import (
    async_setup_config_entry,
    patch_product_identify,
    setup_product_mock,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (blebox_uniapi.error.ConnectionError, ConfigEntryState.SETUP_RETRY),
        (blebox_uniapi.error.HttpError, ConfigEntryState.SETUP_RETRY),
        (blebox_uniapi.error.UnsupportedBoxVersion, ConfigEntryState.SETUP_ERROR),
        (blebox_uniapi.error.UnsupportedBoxResponse, ConfigEntryState.SETUP_ERROR),
        (blebox_uniapi.error.UnauthorizedRequest, ConfigEntryState.SETUP_ERROR),
        (blebox_uniapi.error.Error, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    exception: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test that setup failures map to the correct config entry state."""
    patch_product_identify(None, side_effect=exception)
    await async_setup_config_entry(hass, config_entry)
    assert config_entry.state is expected_state


async def test_setup_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test that UnauthorizedRequest during setup triggers a reauth flow."""
    patch_product_identify(None, side_effect=blebox_uniapi.error.UnauthorizedRequest)
    await async_setup_config_entry(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(
        f["handler"] == "blebox" and f["context"]["source"] == "reauth" for f in flows
    )


async def test_unload_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that unloading works properly."""
    setup_product_mock("switches", [])

    await async_setup_config_entry(hass, config_entry)
    assert hasattr(config_entry, "runtime_data")

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hasattr(config_entry, "runtime_data")

    assert config_entry.state is ConfigEntryState.NOT_LOADED
