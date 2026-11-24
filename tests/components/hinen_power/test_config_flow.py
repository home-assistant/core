"""Test the Hinen config flow."""

from unittest.mock import patch

from hinen_open_api.exceptions import ForbiddenError, HinenAPIError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.application_credentials import DATA_COMPONENT
from homeassistant.components.hinen_power.const import (
    ATTR_AUTH_LANGUAGE,
    ATTR_REGION_CODE,
    DOMAIN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import MockHinen
from .conftest import (
    AUTH_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    HOST,
    OAUTH_CREDENTIAL_NAME,
    PAGE_LANGUAGE,
)

USER_INPUT = {
    CONF_CLIENT_ID: CLIENT_ID,
    CONF_CLIENT_SECRET: CLIENT_SECRET,
    ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
    ATTR_REGION_CODE: "CN",
}


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Check full flow."""
    # Remove the credential imported by the setup_credentials fixture so the
    # test verifies that the flow imports the entered credentials itself.
    manager = hass.data[DATA_COMPONENT]
    for item in manager.async_items():
        await manager.async_delete_item(item["id"])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{AUTH_URL}?state={state}&language={PAGE_LANGUAGE}&key={CLIENT_ID}&redirectUrl=https://example.com/auth/external/callback"
    )

    with (
        patch(
            "homeassistant.components.hinen_power.async_setup_entry", return_value=None
        ),
        patch(
            "homeassistant.components.hinen_power.config_flow.HinenOpen",
            return_value=MockHinen(hass),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth"

        # Simulate the OAuth2 callback with authorization code
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
        assert result["step_id"] == "creation"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == OAUTH_CREDENTIAL_NAME
    assert "result" in result
    assert result["result"].unique_id == "12345678"
    assert result["result"].data["token"]["account_id"] == 12345678
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"
    assert result["result"].data["token"]["host"] == HOST
    assert result["result"].data["token"]["region_code"] == "CN"
    assert CONF_CLIENT_ID not in result["result"].data["token"]
    assert CONF_CLIENT_SECRET not in result["result"].data["token"]

    credentials = manager.async_items()
    assert len(credentials) == 1
    assert credentials[0]["client_id"] == CLIENT_ID
    assert credentials[0]["client_secret"] == CLIENT_SECRET
    assert credentials[0]["name"] == OAUTH_CREDENTIAL_NAME


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_device(
    hass: HomeAssistant,
) -> None:
    """Test flow when no device is found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    # Mock Hinen service with no devices
    service = MockHinen(hass, devices_fixture="get_no_device.json")
    with patch(
        "homeassistant.components.hinen_power.config_flow.HinenOpen",
        return_value=service,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
        assert result["step_id"] == "creation"

        # Simulate the OAuth2 callback with authorization code
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_device"


@pytest.mark.usefixtures("current_request_with_host")
async def test_forbidden_error(
    hass: HomeAssistant,
) -> None:
    """Test flow when ForbiddenError is raised."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    # Mock Hinen service that raises ForbiddenError
    with patch(
        "homeassistant.components.hinen_power.config_flow.HinenOpen.get_device_infos",
        side_effect=ForbiddenError("Access denied"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
        assert result["step_id"] == "creation"

        # Simulate the OAuth2 callback with authorization code
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "access_not_configured"
        assert result["description_placeholders"] == {"message": "Access denied"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test flow when unknown error is raised."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    # Mock Hinen service that raises an unknown error
    with patch(
        "homeassistant.components.hinen_power.config_flow.HinenOpen.get_device_infos",
        side_effect=Exception("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
        assert result["step_id"] == "creation"

        # Simulate the OAuth2 callback with authorization code
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


@pytest.mark.usefixtures("current_request_with_host")
async def test_country_list_api_error(
    hass: HomeAssistant,
) -> None:
    """Test flow when country list API returns error."""
    with patch(
        "homeassistant.components.hinen_power.config_flow.HinenPublic.get_country_list",
        side_effect=HinenAPIError("API error", "error_code"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "failed_to_fetch_countries"


@pytest.mark.usefixtures("current_request_with_host")
async def test_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test flow aborts when the account is already configured."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    with patch(
        "homeassistant.components.hinen_power.config_flow.HinenOpen",
        return_value=MockHinen(hass),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
