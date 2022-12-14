"""Test the Nextcloud config flow."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.nextcloud.config_flow import (
    NextcloudMonitorError,
    UninitializedObject,
)
from homeassistant.components.nextcloud.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch("homeassistant.components.nextcloud.config_flow.NextCloud.setup"), patch(
        "homeassistant.components.nextcloud.config_flow.NextCloud.update"
    ), patch(
        "homeassistant.components.nextcloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "localhost",
                "username": "test-username",
                "password": "test-password",
                "scan_interval": timedelta(seconds=60),
                "verify_ssl": True,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Nextcloud"
    assert result2["data"] == {
        "url": "localhost",
        "username": "test-username",
        "password": "test-password",
        "scan_interval": timedelta(seconds=60),
        "verify_ssl": True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_setup(hass: HomeAssistant) -> None:
    """Test we handle invalid setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nextcloud.config_flow.NextCloud.setup",
        side_effect=NextcloudMonitorError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "localhost",
                "username": "test-username",
                "password": "test-password",
                "scan_interval": timedelta(seconds=60),
                "verify_ssl": True,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_update(hass: HomeAssistant) -> None:
    """Test we handle invalid update."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nextcloud.config_flow.NextCloud.setup",
    ), patch(
        "homeassistant.components.nextcloud.config_flow.NextCloud.update",
        side_effect=UninitializedObject,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "localhost",
                "username": "test-username",
                "password": "test-password",
                "scan_interval": timedelta(seconds=60),
                "verify_ssl": True,
            },
        )
        await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Nextcloud"
    assert result2["data"] == {
        "url": "localhost",
        "username": "test-username",
        "password": "test-password",
        "scan_interval": timedelta(seconds=60),
        "verify_ssl": True,
    }

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
