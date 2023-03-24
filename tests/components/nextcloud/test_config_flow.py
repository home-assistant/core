"""Tests for the Nextcloud config flow."""
from unittest.mock import Mock, patch

from nextcloudmonitor import NextcloudMonitorError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nextcloud import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

VALID_CONFIG = {CONF_URL: "nc_url", CONF_USERNAME: "nc_user", CONF_PASSWORD: "nc_pass"}


async def test_user_create_entry(
    hass: HomeAssistant, mock_nextcloud_monitor: Mock, snapshot: SnapshotAssertion
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        side_effect=NextcloudMonitorError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_error"}

    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        return_value=mock_nextcloud_monitor,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "nc_url"
    assert result["data"] == snapshot


async def test_user_already_configured(
    hass: HomeAssistant, mock_nextcloud_monitor: Mock
) -> None:
    """Test that errors are shown when duplicates are added."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="nc_url",
        unique_id="nc_url",
        data=VALID_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        return_value=mock_nextcloud_monitor,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import(
    hass: HomeAssistant, mock_nextcloud_monitor: Mock, snapshot: SnapshotAssertion
) -> None:
    """Test that the import step works."""
    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        return_value=mock_nextcloud_monitor,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=VALID_CONFIG,
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "nc_url"
    assert result["data"] == snapshot


async def test_import_already_configured(
    hass: HomeAssistant, mock_nextcloud_monitor: Mock
) -> None:
    """Test that import step is aborted when duplicates are added."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="nc_url",
        unique_id="nc_url",
        data=VALID_CONFIG,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        return_value=mock_nextcloud_monitor,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_connection_error(hass: HomeAssistant) -> None:
    """Test that import step is aborted on connection error."""
    with patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitor",
        side_effect=NextcloudMonitorError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=VALID_CONFIG,
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "connection_error_during_import"
