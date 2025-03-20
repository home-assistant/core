"""Tests for the AdGuard Home config flow."""

import aiohttp

from homeassistant import config_entries
from homeassistant.components.adguard.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
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
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on AdGuard Home connection error."""
    aioclient_mock.get(
        (
            f"{'https' if FIXTURE_USER_INPUT[CONF_SSL] else 'http'}"
            f"://{FIXTURE_USER_INPUT[CONF_HOST]}"
            f":{FIXTURE_USER_INPUT[CONF_PORT]}/control/status"
        ),
        exc=aiohttp.ClientError,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_full_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test registering an integration and finishing flow works."""
    aioclient_mock.get(
        (
            f"{'https' if FIXTURE_USER_INPUT[CONF_SSL] else 'http'}"
            f"://{FIXTURE_USER_INPUT[CONF_HOST]}"
            f":{FIXTURE_USER_INPUT[CONF_PORT]}/control/status"
        ),
        json={"version": "v0.99.0"},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result
    assert result["flow_id"]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )
    assert result
    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.title == FIXTURE_USER_INPUT[CONF_HOST]
    assert config_entry.data == {
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_SSL: FIXTURE_USER_INPUT[CONF_SSL],
        CONF_USERNAME: FIXTURE_USER_INPUT[CONF_USERNAME],
        CONF_VERIFY_SSL: FIXTURE_USER_INPUT[CONF_VERIFY_SSL],
    }
    assert not config_entry.options


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
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_hassio_already_configured(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN, data={"host": "mock-adguard", "port": "3000"}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "AdGuard Home Addon",
                "host": "mock-adguard",
                "port": "3000",
            },
            name="AdGuard Home Addon",
            slug="adguard",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_hassio_ignored(hass: HomeAssistant) -> None:
    """Test we supervisor discovered instance can be ignored."""
    MockConfigEntry(domain=DOMAIN, source=config_entries.SOURCE_IGNORE).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "AdGuard Home Addon",
                "host": "mock-adguard",
                "port": "3000",
            },
            name="AdGuard Home Addon",
            slug="adguard",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result
    assert result["type"] is FlowResultType.ABORT
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
        data=HassioServiceInfo(
            config={
                "addon": "AdGuard Home Addon",
                "host": "mock-adguard",
                "port": 3000,
            },
            name="AdGuard Home Addon",
            slug="adguard",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "AdGuard Home Addon"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result
    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.title == "AdGuard Home Addon"
    assert config_entry.data == {
        CONF_HOST: "mock-adguard",
        CONF_PASSWORD: None,
        CONF_PORT: 3000,
        CONF_SSL: False,
        CONF_USERNAME: None,
        CONF_VERIFY_SSL: True,
    }


async def test_hassio_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show Hass.io confirm form on AdGuard Home connection error."""
    aioclient_mock.get(
        "http://mock-adguard:3000/control/status", exc=aiohttp.ClientError
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "AdGuard Home Addon",
                "host": "mock-adguard",
                "port": 3000,
            },
            name="AdGuard Home Addon",
            slug="adguard",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["errors"] == {"base": "cannot_connect"}
