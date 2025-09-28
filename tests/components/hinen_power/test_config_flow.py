"""Test the Hinen config flow."""

from unittest.mock import patch

from hinen_open_api.exceptions import ForbiddenError
import pytest

from homeassistant import config_entries
from homeassistant.components.hinen_power.const import (
    ATTR_AUTH_LANGUAGE,
    ATTR_REGION_CODE,
    CONF_DEVICES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import MockHinen
from .conftest import AUTH_URL, CLIENT_ID, CLIENT_SECRET, HOST, PAGE_LANGUAGE, TITLE

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REGION_CODE: "CN",
        },
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{AUTH_URL}?&state={state}&language={PAGE_LANGUAGE}&key={CLIENT_ID}&redirectUrl=https://my.home-assistant.io/redirect/oauth"
    )

    with (
        patch(
            "homeassistant.components.hinen_power.async_setup_entry", return_value=True
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
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "devices"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICES: ["device_12345"]},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == TITLE
        assert "result" in result
        assert result["result"].unique_id == "device_12345"
        assert result["result"].data["token"]["access_token"] == "mock-access-token"
        assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"
        assert result["result"].data["token"]["host"] == HOST
        assert result["result"].data["token"]["region_code"] == "CN"
        assert result["result"].data["token"]["client_secret"] == CLIENT_SECRET
        assert result["options"] == {CONF_DEVICES: ["device_12345"]}


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_update_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth updates existing entry."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REGION_CODE: "CN",
        },
    )

    # Mock Hinen service with device info that matches the existing entry
    service = MockHinen(hass)
    with (
        patch(
            "homeassistant.components.hinen_power.async_setup_entry", return_value=True
        ),
        patch(
            "homeassistant.components.hinen_power.config_flow.HinenOpen",
            return_value=service,
        ),
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
        # Should update and reload the existing entry
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("current_request_with_host")
async def test_options_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test options flow."""
    config_entry.add_to_hass(hass)

    # Simulate successful setup
    with (
        patch(
            "homeassistant.components.hinen_power.async_setup_entry", return_value=True
        ),
        patch(
            "homeassistant.components.hinen_power.config_flow.HinenOpen",
            return_value=MockHinen(hass),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Initiate options flow
    with patch(
        "homeassistant.components.hinen_power.config_flow.HinenOpen",
        return_value=MockHinen(hass),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        # Submit options
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICES: ["device_12345"]},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert config_entry.options == {CONF_DEVICES: ["device_12345"]}


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_device(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test flow when no device is found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REGION_CODE: "CN",
        },
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
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
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REGION_CODE: "CN",
        },
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
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
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REGION_CODE: "CN",
        },
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_confirm(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth confirm step."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM

    # Test with empty user input
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


@pytest.mark.usefixtures("current_request_with_host")
async def test_country_list_api_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test flow when country list API returns error."""
    # Mock country list API to return error
    aioclient_mock.get(
        "https://global.knowledge.celinksmart.com/prod-api/iot-global/app-api/countries",
        status=500,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.usefixtures("current_request_with_host")
async def test_device_selection_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test device selection flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REGION_CODE: "CN",
        },
    )

    # Mock device selection flow
    with patch(
        "homeassistant.components.hinen_power.config_flow.HinenOpen",
        return_value=MockHinen(hass),
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "mock-code"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "devices"

        # Test device selection with multiple devices
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICES: ["device_12345"]},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["options"] == {CONF_DEVICES: ["device_12345"]}
