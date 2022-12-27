"""Test the Nextcloud config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.nextcloud import NextcloudMonitorError
from homeassistant.components.nextcloud.const import DOMAIN
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def _patch_setup():
    return patch("homeassistant.components.nextcloud.async_setup", return_value=True)


def _patch_tryConnect():
    return patch(
        "homeassistant.components.nextcloud.config_flow.NextCloudFlowHandler._async_try_connect",
        return_value=True,
    )


def _initiate_flow(hass: HomeAssistant):
    setup.async_setup_component(hass, "persistent_notification", {})
    result = hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return result


async def test_successful_connection(hass: HomeAssistant):
    """This test patches the connection test to simulate a successful connection to the nextclodu API."""
    result = await _initiate_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.async_setup", return_value=True
    ), patch(
        "homeassistant.components.nextcloud.config_flow.NextCloudFlowHandler._async_try_connect",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Nextcloud",
                CONF_URL: "test-url",
                CONF_USERNAME: "test-user",
                CONF_PASSWORD: "test-password",
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            CONF_NAME: "Nextcloud",
            CONF_URL: "test-url",
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
            CONF_VERIFY_SSL: True,
        }


async def test_connection_method(hass: HomeAssistant):
    """This test patches the NextcloudMonitorWrapper class to test the connection test method."""
    result = await _initiate_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.async_setup", return_value=True
    ), patch(
        "homeassistant.components.nextcloud.config_flow.NextCloudFlowHandler._async_endpoint_existed",
        return_value=False,
    ), patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitorWrapper",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Nextcloud",
                CONF_URL: "test-url",
                CONF_USERNAME: "test-user",
                CONF_PASSWORD: "test-password",
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            CONF_NAME: "Nextcloud",
            CONF_URL: "test-url",
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
            CONF_VERIFY_SSL: True,
        }

    result = await _initiate_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.async_setup", return_value=True
    ), patch(
        "homeassistant.components.nextcloud.config_flow.NextCloudFlowHandler._async_endpoint_existed",
        return_value=False,
    ), patch(
        "homeassistant.components.nextcloud.NextcloudMonitorWrapper",
        return_value=None,
        side_effect=NextcloudMonitorError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Nextcloud",
                CONF_URL: "test-url",
                CONF_USERNAME: "test-user",
                CONF_PASSWORD: "test-password",
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()
        assert "data" not in result2.keys()


async def test_duplicated_entry(hass: HomeAssistant):
    """This test the NextcloudMonitorWrapper class to test the connection test method."""

    # first entry must be successful
    result = await _initiate_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.async_setup", return_value=True
    ), patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitorWrapper",
        return_value=None,
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Nextcloud",
                CONF_URL: "test-url",
                CONF_USERNAME: "test-user",
                CONF_PASSWORD: "test-password",
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            CONF_NAME: "Nextcloud",
            CONF_URL: "test-url",
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
            CONF_VERIFY_SSL: True,
        }

    # second entry must fail
    result = await _initiate_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    result = await _initiate_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextcloud.async_setup", return_value=True
    ), patch(
        "homeassistant.components.nextcloud.config_flow.NextcloudMonitorWrapper",
        return_value=None,
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Nextcloud",
                CONF_URL: "test-url",
                CONF_USERNAME: "test-user",
                CONF_PASSWORD: "test-password",
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.FORM
        assert "data" not in result2.keys()
