"""Test config flow for Twitch."""
from unittest.mock import patch

from homeassistant.components import sensor
from homeassistant.components.twitch.const import CONF_CHANNELS, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.components.twitch import TwitchMock
from tests.components.twitch.conftest import (
    CLIENT_ID,
    SCOPES,
    TWITCH_AUTHORIZE_URI,
    ComponentSetup,
)
from tests.components.twitch.test_sensor import LEGACY_CONFIG
from tests.typing import ClientSessionGenerator


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        "twitch", context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{TWITCH_AUTHORIZE_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with patch(
        "homeassistant.components.twitch.async_setup_entry", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.twitch.sensor.Twitch", return_value=TwitchMock()
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch", return_value=TwitchMock()
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "channels"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_CHANNELS: ["internetofthings"]}
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] == "create_entry"
    assert result["title"] == "channel123"
    assert "result" in result
    assert "token" in result["result"].data
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"
    assert result["options"] == {CONF_CHANNELS: ["internetofthings"]}


async def test_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Test we abort if already configured."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{TWITCH_AUTHORIZE_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_user_not_found(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Test if the user can't be found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{TWITCH_AUTHORIZE_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch",
        return_value=TwitchMock(user_found=False),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] == FlowResultType.ABORT
        assert result.get("reason") == "user_not_found"


async def test_legacy_migration_already_exists(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test if there already exists a twitch instance and abort."""
    await setup_integration()
    with patch(
        "homeassistant.components.twitch.sensor.Twitch", return_value=TwitchMock()
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=LEGACY_CONFIG[sensor.DOMAIN]
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"
