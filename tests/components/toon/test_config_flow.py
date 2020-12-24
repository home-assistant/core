"""Tests for the Toon config flow."""
from toonapi import Agreement, ToonError

from homeassistant import data_entry_flow
from homeassistant.components.toon.const import CONF_AGREEMENT, CONF_MIGRATE, DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def setup_component(hass):
    """Set up Toon component."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )

    with patch("os.path.isfile", return_value=False):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {CONF_CLIENT_ID: "client", CONF_CLIENT_SECRET: "secret"}},
        )
        await hass.async_block_till_done()


async def test_abort_if_no_configuration(hass):
    """Test abort if no app is configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "missing_configuration"


async def test_full_flow_implementation(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Test registering an integration and finishing flow works."""
    await setup_component(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pick_implementation"

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "eneco"}
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result2["url"] == (
        "https://api.toon.eu/authorize"
        "?response_type=code&client_id=client"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&tenant_id=eneco&issuer=identity.toon.eu"
    )

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        "https://api.toon.eu/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch("toonapi.Toon.agreements", return_value=[Agreement(agreement_id=123)]):
        result3 = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result3["data"]["auth_implementation"] == "eneco"
    assert result3["data"]["agreement_id"] == 123
    result3["data"]["token"].pop("expires_at")
    assert result3["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }


async def test_no_agreements(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Test abort when there are no displays."""
    await setup_component(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "eneco"}
    )

    client = await aiohttp_client(hass.http.app)
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(
        "https://api.toon.eu/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch("toonapi.Toon.agreements", return_value=[]):
        result3 = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result3["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result3["reason"] == "no_agreements"


async def test_multiple_agreements(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Test abort when there are no displays."""
    await setup_component(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "eneco"}
    )

    client = await aiohttp_client(hass.http.app)
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://api.toon.eu/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "toonapi.Toon.agreements",
        return_value=[Agreement(agreement_id=1), Agreement(agreement_id=2)],
    ):
        result3 = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result3["step_id"] == "agreement"

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AGREEMENT: "None None, None"}
        )
        assert result4["data"]["auth_implementation"] == "eneco"
        assert result4["data"]["agreement_id"] == 1


async def test_agreement_already_set_up(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Test showing display form again if display already exists."""
    await setup_component(hass)
    MockConfigEntry(domain=DOMAIN, unique_id=123).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "eneco"}
    )

    client = await aiohttp_client(hass.http.app)
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(
        "https://api.toon.eu/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch("toonapi.Toon.agreements", return_value=[Agreement(agreement_id=123)]):
        result3 = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result3["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result3["reason"] == "already_configured"


async def test_toon_abort(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Test we abort on Toon error."""
    await setup_component(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "eneco"}
    )

    client = await aiohttp_client(hass.http.app)
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(
        "https://api.toon.eu/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch("toonapi.Toon.agreements", side_effect=ToonError):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result2["reason"] == "connection_error"


async def test_import(hass, current_request_with_host):
    """Test if importing step works."""
    await setup_component(hass)

    # Setting up the component without entries, should already have triggered
    # it. Hence, expect this to throw an already_in_progress.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_in_progress"


async def test_import_migration(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Test if importing step with migration works."""
    old_entry = MockConfigEntry(domain=DOMAIN, unique_id=123, version=1)
    old_entry.add_to_hass(hass)

    await setup_component(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].version == 1

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"][CONF_MIGRATE] == old_entry.entry_id

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flows[0]["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {"implementation": "eneco"}
    )

    client = await aiohttp_client(hass.http.app)
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(
        "https://api.toon.eu/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch("toonapi.Toon.agreements", return_value=[Agreement(agreement_id=123)]):
        result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"])

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].version == 2
