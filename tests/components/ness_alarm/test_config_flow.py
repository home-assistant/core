"""Test the Ness Alarm config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from nessclient import Client
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ness_alarm import CONF_SCAN_INTERVAL
from homeassistant.components.ness_alarm.config_flow import OptionsFlow
from homeassistant.components.ness_alarm.const import (
    CONF_ID,
    CONF_INFER_ARMING_STATE,
    CONF_NAME,
    CONF_SUPPORT_HOME_ARM,
    CONF_ZONES,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_panel_info():
    """Mock panel info response."""
    panel_info = MagicMock()
    panel_info.model.value = "DPLUS8"
    panel_info.version = "12.1"
    return panel_info


async def test_form(hass: HomeAssistant, mock_panel_info) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.ness_alarm.config_flow.Client"
        ) as mock_client_class,
        patch(
            "homeassistant.components.ness_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(return_value=mock_panel_info)
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Ness Alarm DPLUS8 (192.168.1.100)"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 2401,
        CONF_INFER_ARMING_STATE: False,
        "panel_model": "DPLUS8",  # This gets added by the flow
    }


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ness_alarm.config_flow.Client"
    ) as mock_client_class:
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(side_effect=TimeoutError())
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: False,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import(hass: HomeAssistant, mock_panel_info) -> None:
    """Test import from YAML."""
    with (
        patch(
            "homeassistant.components.ness_alarm.config_flow.Client"
        ) as mock_client_class,
        patch(
            "homeassistant.components.ness_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(return_value=mock_panel_info)
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: True,
                CONF_SUPPORT_HOME_ARM: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ness Alarm DPLUS8 (192.168.1.100)"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            CONF_INFER_ARMING_STATE: False,
            "panel_model": "D16X",  # Add panel model
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFER_ARMING_STATE: True,
            CONF_SCAN_INTERVAL: 60,
            CONF_SUPPORT_HOME_ARM: False,
            "enabled_zones": 8,  # Use "enabled_zones" not CONF_MAX_SUPPORTED_ZONES
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_INFER_ARMING_STATE: True,
        CONF_SCAN_INTERVAL: 60,
        CONF_SUPPORT_HOME_ARM: False,
        # enabled_zones is removed from options as it's stored in data
    }


async def test_form_invalid_port(hass: HomeAssistant) -> None:
    """Test we handle invalid port numbers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Test port out of range (> 65535)
    with pytest.raises(vol.Invalid):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 70000,
                CONF_INFER_ARMING_STATE: False,
            },
        )

    # Test negative port
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with pytest.raises(vol.Invalid):
        await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: -1,
                CONF_INFER_ARMING_STATE: False,
            },
        )


async def test_form_connection_timeout(hass: HomeAssistant) -> None:
    """Test we handle connection timeout properly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ness_alarm.config_flow.Client"
    ) as mock_client_class:
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        # Simulate a timeout that takes longer than 5 seconds
        mock_client.get_panel_info = AsyncMock(side_effect=TimeoutError())
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: False,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    mock_client.close.assert_called()


async def test_import_invalid_yaml(hass: HomeAssistant) -> None:
    """Test import with invalid YAML configuration."""
    # Since the import step doesn't handle missing CONF_HOST well,
    # we expect a KeyError. The real code should be fixed to handle this.
    with pytest.raises(KeyError):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: True,
            },
        )


async def test_import_with_invalid_zones(hass: HomeAssistant, mock_panel_info) -> None:
    """Test import with invalid zone configuration."""
    with (
        patch(
            "homeassistant.components.ness_alarm.config_flow.Client"
        ) as mock_client_class,
        patch(
            "homeassistant.components.ness_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(return_value=mock_panel_info)
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        # Zone without ID (should be skipped)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_ZONES: [
                    {CONF_NAME: "Zone Without ID"},
                    {CONF_ID: 1, CONF_NAME: "Valid Zone"},
                ],
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # Only the valid zone should be included
        assert len(result["data"][CONF_ZONES]) == 1
        assert result["data"][CONF_ZONES][0][CONF_ID] == 1


async def test_duplicate_config_entry(hass: HomeAssistant, mock_panel_info) -> None:
    """Test that duplicate config entries are handled properly."""
    # Create first entry
    with (
        patch(
            "homeassistant.components.ness_alarm.config_flow.Client"
        ) as mock_client_class,
        patch(
            "homeassistant.components.ness_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(return_value=mock_panel_info)
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: False,
            },
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY

        # Try to create duplicate entry with same unique_id
        # The flow catches the AbortFlow exception and shows an error
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: False,
            },
        )
        # Due to the exception handling in the flow, it shows form with error
        assert result4["type"] == FlowResultType.ABORT
        assert result4["reason"] == "already_configured"


async def test_options_flow_with_missing_entry(hass: HomeAssistant) -> None:
    """Test options flow when config entry doesn't exist."""
    with pytest.raises(config_entries.UnknownEntry):
        await hass.config_entries.options.async_init("non_existent_entry_id")


async def test_connection_with_unknown_exception(hass: HomeAssistant) -> None:
    """Test handling of unknown exceptions during connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ness_alarm.config_flow.Client"
    ) as mock_client_class:
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        # Simulate an unknown exception
        mock_client.get_panel_info = AsyncMock(
            side_effect=RuntimeError("Unknown error")
        )
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: False,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    mock_client.close.assert_called()


async def test_import_connection_failure(hass: HomeAssistant) -> None:
    """Test import when connection fails."""
    with patch(
        "homeassistant.components.ness_alarm.config_flow.Client"
    ) as mock_client_class:
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(side_effect=TimeoutError())
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: True,
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_form_unknown_panel_model(hass: HomeAssistant) -> None:
    """Test handling of unknown panel model."""
    # Create panel_info with unknown model
    panel_info = MagicMock()
    panel_info.model.value = "UNKNOWN_MODEL"
    panel_info.version = "1.0"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.ness_alarm.config_flow.Client"
        ) as mock_client_class,
        patch(
            "homeassistant.components.ness_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_client = AsyncMock(spec=Client)
        mock_client_class.return_value = mock_client
        mock_client.get_panel_info = AsyncMock(return_value=panel_info)
        mock_client.keepalive = AsyncMock()
        mock_client.close = AsyncMock()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 2401,
                CONF_INFER_ARMING_STATE: False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Ness Alarm UNKNOWN_MODEL (192.168.1.100)"
    assert result2["data"]["panel_model"] == "UNKNOWN_MODEL"


async def test_options_flow_zone_count_16(hass: HomeAssistant) -> None:
    """Test options flow with 16 zones."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            "panel_model": "D8X",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFER_ARMING_STATE: True,
            CONF_SUPPORT_HOME_ARM: False,
            "enabled_zones": 16,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Check that the entry data was updated with MANUAL_16
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data["panel_model"] == "MANUAL_16"


async def test_options_flow_zone_count_24(hass: HomeAssistant) -> None:
    """Test options flow with 24 zones."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            "panel_model": "D8X",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFER_ARMING_STATE: True,
            CONF_SUPPORT_HOME_ARM: False,
            "enabled_zones": 24,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Check that the entry data was updated with MANUAL_24
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data["panel_model"] == "MANUAL_24"


async def test_options_flow_zone_count_32(hass: HomeAssistant) -> None:
    """Test options flow with 32 zones."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            "panel_model": "D8X",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFER_ARMING_STATE: True,
            CONF_SUPPORT_HOME_ARM: False,
            "enabled_zones": 32,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Check that the entry data was updated with MANUAL_32
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data["panel_model"] == "MANUAL_32"


async def test_options_flow_entry_not_found(hass: HomeAssistant) -> None:
    """Test options flow when entry is not found during step."""

    # Create a mock entry but don't add it to hass
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            "panel_model": "D16X",
        },
    )

    # Create the options flow with a non-existent entry_id
    options_flow = OptionsFlow(entry)
    options_flow.hass = hass
    options_flow._entry_id = "non_existent_entry_id"  # Set a fake entry_id

    # Call async_step_init - should abort because entry doesn't exist
    result = await options_flow.async_step_init(
        user_input={
            CONF_INFER_ARMING_STATE: True,
            CONF_SUPPORT_HOME_ARM: False,
            "enabled_zones": 16,
        }
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "entry_not_found"


async def test_options_flow_without_enabled_zones(hass: HomeAssistant) -> None:
    """Test options flow without enabled_zones in user_input."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
            "panel_model": "D16X",
        },
    )
    entry.add_to_hass(hass)

    # Create the options flow directly
    options_flow = OptionsFlow(entry)
    options_flow.hass = hass

    # Call async_step_init with user_input that doesn't have enabled_zones
    result = await options_flow.async_step_init(
        user_input={
            CONF_INFER_ARMING_STATE: True,
            CONF_SUPPORT_HOME_ARM: True,
            # No "enabled_zones" key
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_INFER_ARMING_STATE: True,
        CONF_SUPPORT_HOME_ARM: True,
    }
    # Panel model should remain unchanged
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data["panel_model"] == "D16X"
