"""Tests for the Comfoconnect config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.comfoconnect.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import _patch_setup_entry, mocked_bridge, patch_config_flow
from .const import CONF_DATA, DEFAULT_NAME

CONF_IMPORT_DATA = CONF_DATA


# TESTS
async def test_import(hass: HomeAssistant, mocked_bridge) -> None:
    """Test import initialized flow."""
    with patch_config_flow(mocked_bridge), _patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONF_IMPORT_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "configuration.yaml"
    assert result["data"] == CONF_DATA

    # Create same config again, should be rejected due to same host
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONF_IMPORT_DATA,
    )
    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test config flow setup with connection error."""
    with patch("pycomfoconnect.bridge.Bridge.discover") as mock_discover:
        mock_discover.return_value = []

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONF_DATA,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_flow_user_already_configured(
    hass: HomeAssistant,  # config_entry: MockConfigEntry
) -> None:
    """Test user initialized flow with duplicate server."""
    # First create an entry
    with patch_config_flow(mocked_bridge), _patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONF_DATA,
        )
    print(result)

    # Create the integration using the same config data as already created,
    # we should reject the creation due same host
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user(
    hass: HomeAssistant,
    # mocked_bridge: MagicMock,
) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    with patch_config_flow(mocked_bridge), _patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA
