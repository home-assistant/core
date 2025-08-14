"""Test the Hinen config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.hinen.const import (
    ATTR_AUTH_LANGUAGE,
    ATTR_REDIRECTION_URL,
    CONF_DEVICES,
    DOMAIN,
)
from homeassistant.components.hinen.hinen_exception import ForbiddenError, HinenAPIError
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
        "hinen", context={"source": config_entries.SOURCE_USER}
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
            "homeassistant.components.hinen.async_setup_entry", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.hinen.config_flow.HinenOpen",
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
        "hinen", context={"source": config_entries.SOURCE_USER}
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
        patch("homeassistant.components.hinen.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.hinen.config_flow.HinenOpen", return_value=service
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
        "hinen", context={"source": config_entries.SOURCE_USER}
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
        patch("homeassistant.components.hinen.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.hinen.config_flow.HinenOpen", return_value=service
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
        "hinen", context={"source": config_entries.SOURCE_USER}
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
        patch("homeassistant.components.hinen.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.hinen.config_flow.HinenOpen", return_value=service
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
        "homeassistant.components.hinen.config_flow.HinenOpen",
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
