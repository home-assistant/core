"""Test the daikin_onecta config flow."""
from ipaddress import ip_address
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.daikin_onecta.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import SOURCE_ZEROCONF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component

from .conftest import FAKE_ACCESS_TOKEN

from tests.common import MockConfigEntry

CLIENT_ID = "emU20GdJDiiUxI_HnFGz69dD"
CLIENT_SECRET = "TNL1ePwnOkf6o2gKiI8InS8nVwTz2G__VYkv6WznzJGUnwLHLTmKYp-7RZc6FA3yS6D0Wgj_snvqsU5H_LPHQA"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
) -> None:
    """Check full flow."""
    assert await async_setup_component(hass, "daikin_onecta", {})

    await async_import_client_credential(hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET))

    result = await hass.config_entries.flow.async_init("daikin_onecta", context={"source": config_entries.SOURCE_USER})
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&scope=openid+onecta:basic.integration+offline_access"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": FAKE_ACCESS_TOKEN,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch("homeassistant.components.daikin_onecta.async_setup_entry", return_value=True) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_config_entry_unique_id_migration(
    hass: HomeAssistant,
    config_entry_v1_1: MockConfigEntry,
) -> None:
    """Test that old config entries use the unique id obtained from the JWT subject."""
    config_entry_v1_1.add_to_hass(hass)

    assert config_entry_v1_1.unique_id != "1234567890"
    assert config_entry_v1_1.minor_version == 1

    await hass.config_entries.async_setup(config_entry_v1_1.entry_id)
    await hass.async_block_till_done()

    assert config_entry_v1_1.unique_id == "1234567890"
    assert config_entry_v1_1.minor_version == 2


ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("10.0.0.131"),
    ip_addresses=[ip_address("10.0.0.131")],
    hostname="altherma.local.",
    name="altherma.local._tcp.local.",
    port=4321,
    type="_daikin._tcp.local.",
    properties={
        "miconID": "17003904",
        "devID": "[0]",
        "sernum": "172300018",
        "disvers": "1.0.0",
        "fwvers": "436CC152000",
        "areaInfo": "/MNCSEBase/mgo-123456789",
    },
)


async def test_zeroconf_flow(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
) -> None:
    """Test zeroconf flow."""
    assert await async_setup_component(hass, "daikin_onecta", {})

    await async_import_client_credential(hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET))

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&scope=openid+onecta:basic.integration+offline_access"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": FAKE_ACCESS_TOKEN,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    await hass.async_block_till_done()
    assert result["type"] == "external"
    assert result["url"].startswith(OAUTH2_AUTHORIZE)

    with patch("homeassistant.components.daikin_onecta.async_setup_entry", return_value=True) as mock_setup:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_invalid_oauth_token(
    hass: HomeAssistant,
) -> None:
    """Abort when the OAuth access token is not a valid JWT."""
    flow = config_entries.HANDLERS[DOMAIN]()
    flow.hass = hass

    result = await flow.async_oauth_create_entry({"token": {"access_token": "invalid"}})

    assert result["type"] == "abort"
    assert result["reason"] == "invalid_token"


async def test_reauth_confirm_form(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Show the reauthentication confirmation form."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": config_entry.entry_id},
        data=config_entry.data,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"


async def test_zeroconf_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Ignore zeroconf discovery when the integration is already configured."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_zeroconf_without_hostname(hass: HomeAssistant) -> None:
    """Ignore zeroconf discovery without a hostname."""
    discovery = ZeroconfServiceInfo(
        ip_address=ZEROCONF_DISCOVERY.ip_address,
        ip_addresses=ZEROCONF_DISCOVERY.ip_addresses,
        hostname=None,
        name=ZEROCONF_DISCOVERY.name,
        port=ZEROCONF_DISCOVERY.port,
        type=ZEROCONF_DISCOVERY.type,
        properties=ZEROCONF_DISCOVERY.properties,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_reauth_oauth_create_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Update the existing entry after successful reauthentication."""
    hass.config_entries.async_update_entry(config_entry, unique_id="1234567890")
    flow = config_entries.HANDLERS[DOMAIN]()
    flow.hass = hass
    flow.context = {
        "source": config_entries.SOURCE_REAUTH,
        "entry_id": config_entry.entry_id,
    }
    data = {
        "auth_implementation": "cloud",
        "token": {
            "access_token": FAKE_ACCESS_TOKEN,
            "refresh_token": "new-refresh-token",
        },
    }

    with patch.object(hass.config_entries, "async_reload") as reload_entry:
        result = await flow.async_oauth_create_entry(data)

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == data
    reload_entry.assert_called_once_with(config_entry.entry_id)


async def test_reauth_confirm_continue(
    hass: HomeAssistant,
) -> None:
    """Continue reauthentication through the user OAuth step."""
    flow = config_entries.HANDLERS[DOMAIN]()
    flow.hass = hass

    with patch.object(flow, "async_step_user", return_value={"type": "external"}) as step_user:
        result = await flow.async_step_reauth_confirm({})

    assert result == {"type": "external"}
    step_user.assert_awaited_once()
