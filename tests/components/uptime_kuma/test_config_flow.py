"""Tests for the Uptime Kuma config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.uptime_kuma.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

FIXTURE_USER_INPUT = {
    CONF_HOST: "https://uptimekuma.test.com",
    CONF_PORT: 443,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_VERIFY_SSL: True,
}


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on Uptime Kuma connection error."""
    aioclient_mock.get(
        f"{FIXTURE_USER_INPUT[CONF_HOST]}:{FIXTURE_USER_INPUT[CONF_PORT]}",
        text="",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

    assert result
    assert result.get("type") == data_entry_flow.RESULT_TYPE_FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_full_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test registering an integration and finishing flow works."""
    aioclient_mock.get(
        f"{FIXTURE_USER_INPUT[CONF_HOST]}:{FIXTURE_USER_INPUT[CONF_PORT]}",
        json={"version": "v0.99.0"},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result
    assert result.get("flow_id")
    assert result.get("type") == data_entry_flow.RESULT_TYPE_FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )
    assert result2
    assert result2.get("type") == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2.get("title") == FIXTURE_USER_INPUT[CONF_HOST]

    data = result2.get("data")
    assert data
    assert data[CONF_HOST] == FIXTURE_USER_INPUT[CONF_HOST]
    assert data[CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
    assert data[CONF_PORT] == FIXTURE_USER_INPUT[CONF_PORT]
    assert data[CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert data[CONF_VERIFY_SSL] == FIXTURE_USER_INPUT[CONF_VERIFY_SSL]


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "mock-uptime_kuma", CONF_PORT: "443"}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={CONF_HOST: "mock-uptime_kuma", CONF_PORT: "443"},
        context={"source": config_entries.SOURCE_USER},
    )
    assert result
    assert result.get("type") == "abort"
    assert result.get("reason") == "already_configured"
