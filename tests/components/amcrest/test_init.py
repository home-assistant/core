"""Test the Amcrest integration init."""

from unittest.mock import AsyncMock, MagicMock, patch

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_patch_platforms")
async def test_setup_entry_uses_unique_id_for_identifiers_when_serial_fetch_fails(
    hass: HomeAssistant,
) -> None:
    """Test config-entry setup uses entry.unique_id even if device serial fetch fails."""
    entry = MockConfigEntry(
        title="Amcrest Camera",
        domain=DOMAIN,
        unique_id="SERIAL_FROM_FLOW",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_NAME: "Amcrest Camera",
        },
    )
    entry.add_to_hass(hass)

    api = MagicMock()

    async def _raise_serial():
        raise AmcrestError

    api.async_serial_number = _raise_serial()
    api.get_base_url.return_value = "http://1.2.3.4"

    async_forward = AsyncMock()

    with (
        patch("homeassistant.components.amcrest.AmcrestChecker", return_value=api),
        patch("homeassistant.components.amcrest.dr.async_get") as mock_async_get,
        patch("homeassistant.components.amcrest.DeviceInfo") as mock_device_info,
        patch.object(hass.config_entries, "async_forward_entry_setups", async_forward),
    ):
        device_registry = MagicMock()
        mock_async_get.return_value = device_registry

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Device registry should be keyed by the stable unique_id, not entry_id.
    device_registry.async_get_or_create.assert_called_once()
    identifiers = device_registry.async_get_or_create.call_args.kwargs["identifiers"]
    assert identifiers == {(DOMAIN, "SERIAL_FROM_FLOW")}

    # DeviceInfo should also use the stable unique_id.
    assert mock_device_info.call_args.kwargs["identifiers"] == {
        (DOMAIN, "SERIAL_FROM_FLOW")
    }


@pytest.mark.usefixtures("mock_patch_platforms")
async def test_setup_entry_requires_unique_id(hass: HomeAssistant) -> None:
    """Test config-entry setup fails when entry.unique_id is missing."""
    entry = MockConfigEntry(
        title="Amcrest Camera",
        domain=DOMAIN,
        unique_id=None,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_NAME: "Amcrest Camera",
        },
    )
    entry.add_to_hass(hass)

    api = MagicMock()
    api.get_base_url.return_value = "http://1.2.3.4"

    with patch("homeassistant.components.amcrest.AmcrestChecker", return_value=api):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
