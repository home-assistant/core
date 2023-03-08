"""Tests for the Nextcloud config flow."""
from unittest.mock import Mock, patch

from nextcloudmonitor import NextcloudMonitorError

from homeassistant.components.nextcloud import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_create_entry(
    hass: HomeAssistant, mock_nextcloud_monitor: Mock
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        return_value=mock_nextcloud_monitor,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "nc_url", CONF_USERNAME: "nc_user", CONF_PASSWORD: "nc_pass"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "nc_url"
    assert result["data"][CONF_URL] == "nc_url"
    assert result["data"][CONF_USERNAME] == "nc_user"
    assert result["data"][CONF_PASSWORD] == "nc_pass"


async def test_form_already_configured(
    hass: HomeAssistant, mock_nextcloud_monitor: Mock
) -> None:
    """Test that errors are shown when duplicates are added."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="nc_url",
        unique_id="nc_url",
        data={CONF_URL: "nc_url", CONF_USERNAME: "nc_user", CONF_PASSWORD: "nc_pass"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        return_value=mock_nextcloud_monitor,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "nc_url", CONF_USERNAME: "nc_user", CONF_PASSWORD: "nc_pass"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_connection_error(
    hass: HomeAssistant, mock_nextcloud_monitor: Mock
) -> None:
    """Test that errors are shown when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        return_value=mock_nextcloud_monitor,
    ) as ncm_mock:
        ncm_mock.side_effect = NextcloudMonitorError
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "nc_url", CONF_USERNAME: "nc_user", CONF_PASSWORD: "nc_pass"},
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {"base": "connection_error"}


async def test_import(hass: HomeAssistant, mock_nextcloud_monitor: Mock) -> None:
    """Test that the import step works."""
    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        return_value=mock_nextcloud_monitor,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_URL: "nc_url",
                CONF_USERNAME: "nc_user",
                CONF_PASSWORD: "nc_pass",
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "nc_url"
    assert result["data"][CONF_URL] == "nc_url"
    assert result["data"][CONF_USERNAME] == "nc_user"
    assert result["data"][CONF_PASSWORD] == "nc_pass"
