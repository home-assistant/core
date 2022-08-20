"""Test the MicroBot config flow."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType

from . import (
    NOT_MICROBOT_INFO,
    USER_INPUT,
    SERVICE_INFO,
    init_integration,
    patch_async_setup_entry,
)

from tests.common import MockConfigEntry

DOMAIN = "keymitt_ble"


async def test_bluetooth_discovery(hass):
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "mibp"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_ACCESS_TOKEN: "test-token",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_already_setup(hass):
    """Test discovery via bluetooth with a valid device when already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_ACCESS_TOKEN: "test-token",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_not_microbot(hass):
    """Test discovery via bluetooth not switchbot."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=NOT_MICROBOT_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_user_setup(hass):
    """Test the user initiated form with valid mac."""

    with patch(
        "homeassistant.components.keymitt_ble.config_flow.async_discovered_service_info",
        return_value=[SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "mibp"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_ACCESS_TOKEN: "test-token",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_setup_already_configured(hass):
    """Test the user initiated form with password and valid mac."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_ACCESS_TOKEN: "test-token",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.keymitt_ble.config_flow.async_discovered_service_info",
        return_value=[WOHAND_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_unconfigured_devices"


async def test_user_no_devices(hass):
    """Test the user initiated form with password and valid mac."""
    with patch(
        "homeassistant.components.keymitt_ble.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_unconfigured_devices"


async def test_async_step_user_takes_precedence_over_discovery(hass):
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.keymitt_ble.config_flow.async_discovered_service_info",
        return_value=[SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] == FlowResultType.FORM

    with patch_async_setup_entry() as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "mibp"
    assert result2["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_ACCESS_TOKEN: "test-token",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    # Verify the original one was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)
