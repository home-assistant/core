"""Test the melnor config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.melnor.const import DOMAIN
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant

from . import FAKE_DEVICE, FAKE_DEVICE_2, FAKE_MAC, _patch_device, _patch_scanner

INTEGRATION_DISCOVERY = {CONF_MAC: FAKE_MAC}


async def test_none_discovered(hass):
    """Test we short circuit to config entry creation."""

    with _patch_scanner(devices=[]), _patch_device(), patch(
        "homeassistant.components.melnor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        print(result)

        assert result["type"] == "abort"
        assert result["reason"] == "no_devices_found"

    assert len(mock_setup_entry.mock_calls) == 0


async def test_single_discovered(hass):
    """Test we short circuit to config entry creation."""

    with _patch_scanner(devices=[FAKE_DEVICE]), _patch_device(), patch(
        "homeassistant.components.melnor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "create_entry"
        assert result["title"] == FAKE_MAC
        assert result["data"] == {CONF_MAC: FAKE_MAC}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_multiple_discovered(hass: HomeAssistant):
    """Test we get the device picker."""

    with _patch_scanner([FAKE_DEVICE, FAKE_DEVICE_2]), _patch_device(), patch(
        "homeassistant.components.melnor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "pick_device"
        assert result["data_schema"] is not None

    assert len(mock_setup_entry.mock_calls) == 0
