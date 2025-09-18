"""Test the AEH config flow."""

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from azure.eventhub.exceptions import EventHubError
import pytest

from homeassistant import config_entries
from homeassistant.components.azure_event_hub.const import (
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DOMAIN,
    STEP_CONN_STRING,
    STEP_SAS,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    BASE_CONFIG_CS,
    BASE_CONFIG_SAS,
    CS_CONFIG,
    CS_CONFIG_FULL,
    IMPORT_CONFIG,
    SAS_CONFIG,
    SAS_CONFIG_FULL,
    UPDATE_OPTIONS,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.parametrize(
    ("step1_config", "step_id", "step2_config", "data_config"),
    [
        (BASE_CONFIG_CS, STEP_CONN_STRING, CS_CONFIG, CS_CONFIG_FULL),
        (BASE_CONFIG_SAS, STEP_SAS, SAS_CONFIG, SAS_CONFIG_FULL),
    ],
    ids=["connection_string", "sas"],
)
@pytest.mark.usefixtures("mock_from_connection_string")
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    step1_config: dict[str, Any],
    step_id: str,
    step2_config: dict[str, str],
    data_config: dict[str, str],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        step1_config.copy(),
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == step_id
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        step2_config.copy(),
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "test-instance"
    assert result3["data"] == data_config
    mock_setup_entry.assert_called_once()


async def test_import(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    import_config = IMPORT_CONFIG.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=IMPORT_CONFIG.copy(),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-instance"
    options = {
        CONF_SEND_INTERVAL: import_config.pop(CONF_SEND_INTERVAL),
        CONF_MAX_DELAY: import_config.pop(CONF_MAX_DELAY),
    }
    assert result["data"] == import_config
    assert result["options"] == options
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    "source",
    [config_entries.SOURCE_USER, config_entries.SOURCE_IMPORT],
    ids=["user", "import"],
)
async def test_single_instance(hass: HomeAssistant, source: str) -> None:
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CS_CONFIG_FULL,
        title="test-instance",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=BASE_CONFIG_CS.copy(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [(EventHubError("test"), "cannot_connect"), (Exception, "unknown")],
    ids=["cannot_connect", "unknown"],
)
async def test_connection_error_sas(
    hass: HomeAssistant,
    mock_get_eventhub_properties: AsyncMock,
    side_effect: Exception,
    error_message: str,
) -> None:
    """Test we handle connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=BASE_CONFIG_SAS.copy(),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    mock_get_eventhub_properties.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        SAS_CONFIG.copy(),
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error_message}


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [(EventHubError("test"), "cannot_connect"), (Exception, "unknown")],
    ids=["cannot_connect", "unknown"],
)
async def test_connection_error_cs(
    hass: HomeAssistant,
    mock_from_connection_string: MagicMock,
    side_effect: Exception,
    error_message: str,
) -> None:
    """Test we handle connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=BASE_CONFIG_CS.copy(),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    mock_from_connection_string.return_value.get_eventhub_properties.side_effect = (
        side_effect
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CS_CONFIG.copy(),
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error_message}


async def test_options_flow(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test options flow."""
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["last_step"]

    updated = await hass.config_entries.options.async_configure(
        result["flow_id"], UPDATE_OPTIONS
    )
    assert updated["type"] is FlowResultType.CREATE_ENTRY
    assert updated["data"] == UPDATE_OPTIONS
    await hass.async_block_till_done()
