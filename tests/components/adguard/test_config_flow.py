"""Tests for the AdGuard Home config flow."""

from base64 import b64encode
from unittest.mock import patch

import aiohttp
import pytest

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

FIXTURE_STATUS = {
    "version": "v0.99.0",
    "language": "en",
    "dns_addresses": ["127.0.0.1"],
    "dns_port": 53,
    "http_port": 3000,
    "protection_disabled_duration": 0,
    "protection_enabled": True,
    "dhcp_available": True,
    "running": True,
}

FIXTURE_USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 3000,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_SSL: True,
    CONF_VERIFY_SSL: True,
}

URL_STATUS = "https://127.0.0.1:3000/control/status"


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
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, "invalid_auth"),
        (500, "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    error: str,
) -> None:
    """Test we show the error AdGuard Home ends the connection test in."""
    aioclient_mock.get(URL_STATUS, status=status, text="Nope")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}


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
        json=FIXTURE_STATUS,
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
        domain=DOMAIN, data={CONF_HOST: "mock-adguard", CONF_PORT: 3000}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**FIXTURE_USER_INPUT, CONF_HOST: "mock-adguard"},
    )

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
        json=FIXTURE_STATUS,
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


async def test_reauth(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test authenticating again stores the new credentials."""
    entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
    entry.add_to_hass(hass)
    aioclient_mock.get(
        URL_STATUS, json=FIXTURE_STATUS, headers={"Content-Type": CONTENT_TYPE_JSON}
    )

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch("homeassistant.components.adguard.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "frenck", CONF_PASSWORD: "zerocool"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == "frenck"
    assert entry.data[CONF_PASSWORD] == "zerocool"

    # The new credentials are the ones that were tested.
    headers = aioclient_mock.mock_calls[-1][3]
    assert headers["Authorization"] == f"Basic {b64encode(b'frenck:zerocool').decode()}"


@pytest.mark.parametrize(
    ("mock_kwargs", "error"),
    [
        ({"status": 401, "text": "Nope"}, "invalid_auth"),
        ({"exc": aiohttp.ClientError}, "cannot_connect"),
        ({"status": 500, "text": "Nope"}, "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_kwargs: dict,
    error: str,
) -> None:
    """Test authenticating again shows errors, and recovers from them."""
    entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
    entry.add_to_hass(hass)
    aioclient_mock.get(URL_STATUS, **mock_kwargs)

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "frenck", CONF_PASSWORD: "wrong"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        URL_STATUS, json=FIXTURE_STATUS, headers={"Content-Type": CONTENT_TYPE_JSON}
    )

    with patch("homeassistant.components.adguard.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "frenck", CONF_PASSWORD: "zerocool"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
