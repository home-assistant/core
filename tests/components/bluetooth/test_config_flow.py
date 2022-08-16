"""Test the bluetooth config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.bluetooth.const import (
    CONF_ADAPTER,
    DOMAIN,
    MACOS_DEFAULT_BLUETOOTH_ADAPTER,
)
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_async_step_user(hass):
    """Test setting up manually."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "enable_bluetooth"
    with patch(
        "homeassistant.components.bluetooth.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Bluetooth"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_user_only_allows_one(hass):
    """Test setting up manually with an existing entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_integration_discovery(hass):
    """Test setting up from integration discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "enable_bluetooth"
    with patch(
        "homeassistant.components.bluetooth.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Bluetooth"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_integration_discovery_during_onboarding(hass):
    """Test setting up from integration discovery during onboarding."""

    with patch(
        "homeassistant.components.bluetooth.async_setup_entry", return_value=True
    ) as mock_setup_entry, patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={},
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bluetooth"
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_async_step_integration_discovery_already_exists(hass):
    """Test setting up from integration discovery when an entry already exists."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_import(hass):
    """Test setting up from integration discovery."""
    with patch(
        "homeassistant.components.bluetooth.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Bluetooth"
        assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_import_already_exists(hass):
    """Test setting up from yaml when an entry already exists."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@patch("homeassistant.components.bluetooth.util.platform.system", return_value="Linux")
async def test_options_flow_linux(mock_system, hass, mock_bleak_scanner_start):
    """Test options on Linux."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
        unique_id="DOMAIN",
    )
    entry.add_to_hass(hass)

    # Verify we can keep it as hci0
    with patch(
        "bluetooth_adapters.get_bluetooth_adapters", return_value=["hci0", "hci1"]
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_ADAPTER: "hci0",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADAPTER] == "hci0"

    # Verify we can change it to hci1
    with patch(
        "bluetooth_adapters.get_bluetooth_adapters", return_value=["hci0", "hci1"]
    ):
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_ADAPTER: "hci1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADAPTER] == "hci1"


@patch("homeassistant.components.bluetooth.util.platform.system", return_value="Darwin")
async def test_options_flow_macos(mock_system, hass, mock_bleak_scanner_start):
    """Test options on MacOS."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
        unique_id="DOMAIN",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ADAPTER: MACOS_DEFAULT_BLUETOOTH_ADAPTER,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADAPTER] == MACOS_DEFAULT_BLUETOOTH_ADAPTER


@patch(
    "homeassistant.components.bluetooth.util.platform.system", return_value="Windows"
)
async def test_options_flow_windows(mock_system, hass, mock_bleak_scanner_start):
    """Test options on Windows."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
        unique_id="DOMAIN",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_adapters"
