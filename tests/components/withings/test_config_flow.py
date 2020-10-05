"""Tests for config flow."""
from aiohttp.test_utils import TestClient

from homeassistant.components.withings import const
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_EXTERNAL_URL,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import AUTH_CALLBACK_PATH
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_config_non_unique_profile(hass: HomeAssistant) -> None:
    """Test setup a non-unique profile."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN, data={const.PROFILE: "person0"}, unique_id="0"
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "profile"}, data={const.PROFILE: "person0"}
    )

    assert result
    assert result["errors"]["base"] == "profile_exists"


async def test_config_reauth_profile(
    hass: HomeAssistant, aiohttp_client, aioclient_mock
) -> None:
    """Test reauth an existing profile re-creates the config entry."""
    hass_config = {
        HA_DOMAIN: {
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_EXTERNAL_URL: "http://127.0.0.1:8080/",
        },
        const.DOMAIN: {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_USE_WEBHOOK: False,
        },
    }
    await async_process_ha_core_config(hass, hass_config.get(HA_DOMAIN))
    assert await async_setup_component(hass, const.DOMAIN, hass_config)
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(
        domain=const.DOMAIN, data={const.PROFILE: "person0"}, unique_id="0"
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "reauth", "profile": "person0"}
    )
    assert result
    assert result["type"] == "form"
    assert result["step_id"] == "reauth"
    assert result["description_placeholders"] == {const.PROFILE: "person0"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(hass, {"flow_id": result["flow_id"]})

    client: TestClient = await aiohttp_client(hass.http.app)
    resp = await client.get(f"{AUTH_CALLBACK_PATH}?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://account.withings.com/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "userid": "0",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    entries = hass.config_entries.async_entries(const.DOMAIN)
    assert entries
    assert entries[0].data["token"]["refresh_token"] == "mock-refresh-token"
