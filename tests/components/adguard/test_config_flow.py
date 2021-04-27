"""Tests for the AdGuard Home config flow."""
import aiohttp

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.adguard import config_flow
from homeassistant.components.adguard.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

FIXTURE_USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 3000,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_SSL: True,
    CONF_VERIFY_SSL: True,
}


async def test_show_authenticate_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    flow = config_flow.AdGuardHomeFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on AdGuard Home connection error."""
    aioclient_mock.get(
        f"{'https' if FIXTURE_USER_INPUT[CONF_SSL] else 'http'}"
        f"://{FIXTURE_USER_INPUT[CONF_HOST]}"
        f":{FIXTURE_USER_INPUT[CONF_PORT]}/control/status",
        exc=aiohttp.ClientError,
    )

    flow = config_flow.AdGuardHomeFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_full_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test registering an integration and finishing flow works."""
    aioclient_mock.get(
        f"{'https' if FIXTURE_USER_INPUT[CONF_SSL] else 'http'}"
        f"://{FIXTURE_USER_INPUT[CONF_HOST]}"
        f":{FIXTURE_USER_INPUT[CONF_PORT]}/control/status",
        json={"version": "v0.99.0"},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    flow = config_flow.AdGuardHomeFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == FIXTURE_USER_INPUT[CONF_HOST]
    assert result["data"][CONF_HOST] == FIXTURE_USER_INPUT[CONF_HOST]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
    assert result["data"][CONF_PORT] == FIXTURE_USER_INPUT[CONF_PORT]
    assert result["data"][CONF_SSL] == FIXTURE_USER_INPUT[CONF_SSL]
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_VERIFY_SSL] == FIXTURE_USER_INPUT[CONF_VERIFY_SSL]


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN, data={"host": "mock-adguard", "port": "3000"}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={"host": "mock-adguard", "port": "3000"},
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_hassio_already_configured(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN, data={"host": "mock-adguard", "port": "3000"}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={"addon": "AdGuard Home Addon", "host": "mock-adguard", "port": "3000"},
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_hassio_ignored(hass: HomeAssistant) -> None:
    """Test we supervisor discovered instance can be ignored."""
    MockConfigEntry(domain=DOMAIN, source=config_entries.SOURCE_IGNORE).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={"addon": "AdGuard Home Addon", "host": "mock-adguard", "port": "3000"},
        context={"source": config_entries.SOURCE_HASSIO},
    )

    assert "type" in result
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert "reason" in result
    assert result["reason"] == "already_configured"


async def test_hassio_confirm(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we can finish a config flow."""
    aioclient_mock.get(
        "http://mock-adguard:3000/control/status",
        json={"version": "v0.99.0"},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={"addon": "AdGuard Home Addon", "host": "mock-adguard", "port": 3000},
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "AdGuard Home Addon"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "AdGuard Home Addon"
    assert result["data"][CONF_HOST] == "mock-adguard"
    assert result["data"][CONF_PASSWORD] is None
    assert result["data"][CONF_PORT] == 3000
    assert result["data"][CONF_SSL] is False
    assert result["data"][CONF_USERNAME] is None
    assert result["data"][CONF_VERIFY_SSL]


async def test_hassio_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show Hass.io confirm form on AdGuard Home connection error."""
    aioclient_mock.get(
        "http://mock-adguard:3000/control/status", exc=aiohttp.ClientError
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={"addon": "AdGuard Home Addon", "host": "mock-adguard", "port": 3000},
        context={"source": config_entries.SOURCE_HASSIO},
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["errors"] == {"base": "cannot_connect"}
