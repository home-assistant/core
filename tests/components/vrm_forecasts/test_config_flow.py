"""Test the Victron VRM Solar Forecast config flow."""

import datetime
from unittest.mock import AsyncMock, patch

from victron_vrm.exceptions import AuthenticationError, VictronVRMError
from victron_vrm.models import Site

from homeassistant import config_entries
from homeassistant.components.vrm_forecasts.const import (
    CONF_API_KEY,
    CONF_SITE_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

AUTH_DEMO_URL = "https://vrmapi.victronenergy.com/v2/auth/loginAsDemo"
VRM_TEST_SITE = Site(
    idSite=123456,
    name="ESS System",
    timezone="Europe/Amsterdam",
    identifier="abcde12345",
    geofenceEnabled=False,
    realtimeUpdates=True,
    hasGenerator=False,
    hasMains=True,
    alarmMonitoring=0,
    invalidVRMAuthTokenUsedInLogRequest=False,
    syscreated=datetime.datetime.now(),
    shared=False,
)


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        return_value=VRM_TEST_SITE,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test_token",
                CONF_SITE_ID: VRM_TEST_SITE.id,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"VRM Forecast for {VRM_TEST_SITE.name}"
    assert result["data"] == {
        CONF_API_KEY: "test_token",
        CONF_SITE_ID: VRM_TEST_SITE.id,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        side_effect=AuthenticationError("PyTest Patch", status_code=401),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "invalid_token",
                CONF_SITE_ID: 123456,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        return_value=VRM_TEST_SITE,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test_token",
                CONF_SITE_ID: VRM_TEST_SITE.id,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"VRM Forecast for {VRM_TEST_SITE.name}"
    assert result["data"] == {
        CONF_API_KEY: "test_token",
        CONF_SITE_ID: VRM_TEST_SITE.id,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        side_effect=VictronVRMError("PyTest Patch", status_code=500, response_data={}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "invalid_token",
                CONF_SITE_ID: 123456,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        return_value=VRM_TEST_SITE,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test_token",
                CONF_SITE_ID: VRM_TEST_SITE.id,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"VRM Forecast for {VRM_TEST_SITE.name}"
    assert result["data"] == {
        CONF_API_KEY: "test_token",
        CONF_SITE_ID: VRM_TEST_SITE.id,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_site_not_found(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle site not found error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "invalid_token",
                CONF_SITE_ID: 123456,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "site_not_found"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        return_value=VRM_TEST_SITE,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test_token",
                CONF_SITE_ID: VRM_TEST_SITE.id,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"VRM Forecast for {VRM_TEST_SITE.name}"
    assert result["data"] == {
        CONF_API_KEY: "test_token",
        CONF_SITE_ID: VRM_TEST_SITE.id,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_insufficient_permissions(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle insufficient permissions error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        side_effect=VictronVRMError(
            "PyTest Patch",
            status_code=403,
            response_data={},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "invalid_token",
                CONF_SITE_ID: 123456,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        return_value=VRM_TEST_SITE,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test_token",
                CONF_SITE_ID: VRM_TEST_SITE.id,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"VRM Forecast for {VRM_TEST_SITE.name}"
    assert result["data"] == {
        CONF_API_KEY: "test_token",
        CONF_SITE_ID: VRM_TEST_SITE.id,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unexpected_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "invalid_token",
                CONF_SITE_ID: 123456,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.vrm_forecasts.config_flow.VRMClientHolder.get_site",
        return_value=VRM_TEST_SITE,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test_token",
                CONF_SITE_ID: VRM_TEST_SITE.id,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"VRM Forecast for {VRM_TEST_SITE.name}"
    assert result["data"] == {
        CONF_API_KEY: "test_token",
        CONF_SITE_ID: VRM_TEST_SITE.id,
    }
    assert len(mock_setup_entry.mock_calls) == 1
