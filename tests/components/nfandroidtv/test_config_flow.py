"""Test NFAndroidTV config flow."""

from unittest.mock import AsyncMock, MagicMock

from notifications_android_tv.notifications import ConnectError
import pytest

from homeassistant.components.nfandroidtv.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CONF_CONFIG_FLOW, CONF_DATA, NAME

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_notifications_android_tv")
async def test_flow_user(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test user initialized flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_CONFIG_FLOW,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == CONF_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_notifications_android_tv")
async def test_flow_user_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test user initialized flow with duplicate server."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_CONFIG_FLOW,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error_msg"),
    [(ConnectError, "cannot_connect"), (ValueError, "unknown")],
)
async def test_flow_user_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_notifications_android_tv: MagicMock,
    exception: Exception,
    error_msg: str,
) -> None:
    """Test user initialized flow with errors."""

    mock_notifications_android_tv.cls.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONF_CONFIG_FLOW
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_msg}

    mock_notifications_android_tv.cls.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONF_CONFIG_FLOW
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == CONF_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_notifications_android_tv")
async def test_flow_reconfigure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""

    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "4.3.2.1"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "4.3.2.1"

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("exception", "error"), [(ConnectError, "cannot_connect"), (ValueError, "unknown")]
)
async def test_flow_reconfigure_errors(
    hass: HomeAssistant,
    mock_notifications_android_tv: MagicMock,
    config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reconfigure flow errors."""

    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_notifications_android_tv.cls.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "4.3.2.1"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_notifications_android_tv.cls.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "4.3.2.1"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "4.3.2.1"

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("mock_notifications_android_tv")
async def test_flow_reconfigure_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow aborts if already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        title="Android TV / Fire TV (4.3.2.1)",
        data={CONF_HOST: "4.3.2.1"},
        entry_id="987654321",
    ).add_to_hass(hass)

    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "4.3.2.1"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert len(hass.config_entries.async_entries()) == 2
