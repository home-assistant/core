"""Test the Hinen config flow."""

from unittest.mock import patch

from hinen_open_api.exceptions import ForbiddenError, HinenAPIError
import pytest

from homeassistant import config_entries
from homeassistant.components.hinen_power.const import (
    ATTR_AUTH_LANGUAGE,
    ATTR_REDIRECTION_URL,
    CONF_DEVICES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import MockHinen
from .conftest import (
    AUTH_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    HOST,
    PAGE_LANGUAGE,
    REGION_CODE,
    TITLE,
    ComponentSetup,
)

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REDIRECTION_URL: "https://example.com",
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
        f"{AUTH_URL}?&state={state}&language={PAGE_LANGUAGE}&key={CLIENT_ID}"
        "&redirectUrl=https://example.com/auth/hinen/callback"
    )

    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/hinen/callback?code=test_code&state={state}&regionCode=CN&clientSecret=test_client_secret"
    )
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with (
        patch(
            "homeassistant.components.hinen_power.async_setup_entry", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.hinen_power.config_flow.HinenOpen",
            return_value=MockHinen(hass),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "devices"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICES: ["device_12345"]}
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert "result" in result
    assert result["result"].unique_id == "device_12345"
    assert "token" in result["result"].data
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"
    assert result["result"].data["token"]["host"] == HOST
    assert result["result"].data["token"]["region_code"] == REGION_CODE
    assert result["result"].data["token"]["client_secret"] == CLIENT_SECRET
    assert result["options"] == {CONF_DEVICES: ["device_12345"]}


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_abort_without_device(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REDIRECTION_URL: "https://example.com",
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
        f"{AUTH_URL}?&state={state}&language={PAGE_LANGUAGE}&key={CLIENT_ID}"
        "&redirectUrl=https://example.com/auth/hinen/callback"
    )

    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/hinen/callback?code=test_code&state={state}&regionCode=CN&clientSecret=test_client_secret"
    )
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    service = MockHinen(hass, devices_fixture="get_no_device.json")
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
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_device"


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_with_forbidden_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REDIRECTION_URL: "https://example.com",
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
        f"{AUTH_URL}?&state={state}&language={PAGE_LANGUAGE}&key={CLIENT_ID}"
        "&redirectUrl=https://example.com/auth/hinen/callback"
    )

    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/hinen/callback?code=test_code&state={state}&regionCode=CN&clientSecret=test_client_secret"
    )
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    async def mock_get_device_infos():
        raise ForbiddenError("Access denied")
        yield  # pylint: disable=unreachable

    service = MockHinen(hass)
    service.get_device_infos = mock_get_device_infos

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
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "access_not_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_with_unknown_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REDIRECTION_URL: "https://example.com",
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
        f"{AUTH_URL}?&state={state}&language={PAGE_LANGUAGE}&key={CLIENT_ID}"
        "&redirectUrl=https://example.com/auth/hinen/callback"
    )

    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/hinen/callback?code=test_code&state={state}&regionCode=CN&clientSecret=test_client_secret"
    )
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    async def mock_get_device_infos():
        raise HinenAPIError("unknown error")
        yield  # pylint: disable=unreachable

    service = MockHinen(hass)
    service.get_device_infos = mock_get_device_infos

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
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


@pytest.mark.usefixtures("current_request_with_host")
async def test_options_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_integration: ComponentSetup,
) -> None:
    """Test options flow."""
    await setup_integration()

    with patch(
        "homeassistant.components.hinen_power.config_flow.HinenOpen",
        return_value=MockHinen(hass),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_DEVICES: ["device_12345"]}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_DEVICES: ["device_12345"]}


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


@pytest.mark.usefixtures("current_request_with_host")
async def test_unique_id_mismatch_during_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test unique ID mismatch during reauth."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    # Configure user step with different redirection URL
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REDIRECTION_URL: "https://different-example.com",
        },
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://different-example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/hinen/callback?code=test_code&state={state}&regionCode=CN&clientSecret=test_client_secret"
    )
    assert resp.status == 200

    # Mock a service with a different device ID to trigger unique ID mismatch
    service = MockHinen(hass, devices_fixture="get_different_device.json")
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
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "wrong_account"


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_device_during_oauth_create_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test no device during OAuth create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            ATTR_AUTH_LANGUAGE: PAGE_LANGUAGE,
            ATTR_REDIRECTION_URL: "https://example.com",
        },
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/hinen/callback?code=test_code&state={state}&regionCode=CN&clientSecret=test_client_secret"
    )
    assert resp.status == 200

    service = MockHinen(hass, devices_fixture="get_no_device.json")
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
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_device"


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_device_during_options_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_integration: ComponentSetup,
) -> None:
    """Test no device during options flow."""
    await setup_integration()

    service = MockHinen(hass, devices_fixture="get_no_device.json")
    with patch(
        "homeassistant.components.hinen_power.config_flow.HinenOpen",
        return_value=service,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_device"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_update_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
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
            ATTR_REDIRECTION_URL: "https://example.com",
        },
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    # Simulate callback from OAuth provider
    client = await hass_client_no_auth()
    resp = await client.get(
        f"/auth/hinen/callback?code=test_code&state={state}&regionCode=CN&clientSecret=test_client_secret"
    )
    assert resp.status == 200

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
        # Should update and reload the existing entry
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
