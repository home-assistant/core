"""Tests for the AdGuard Home config flow."""

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.adguard.config_flow import _parse_address
from homeassistant.components.adguard.const import DEFAULT_BASE_PATH, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
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
    CONF_URL: "127.0.0.1:3000",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
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
        "http://127.0.0.1:3000/control/status",
        exc=aiohttp.ClientError,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        (
            "adguard.local",
            ("adguard.local", 3000, DEFAULT_BASE_PATH, False),
        ),
        (
            "adguard.local:3001",
            ("adguard.local", 3001, DEFAULT_BASE_PATH, False),
        ),
        (
            "https://adguard.local",
            ("adguard.local", 443, DEFAULT_BASE_PATH, True),
        ),
        (
            "http://adguard.local",
            ("adguard.local", 80, DEFAULT_BASE_PATH, False),
        ),
        (
            "https://adguard.local/custom/path",
            ("adguard.local", 443, "/custom/path", True),
        ),
    ],
)
def test_parse_address_valid(address: str, expected: tuple[str, int, str, bool]) -> None:
    """Test valid address formats are parsed correctly."""
    assert _parse_address(address) == expected


@pytest.mark.parametrize(
    "address",
    [
        "ftp://adguard.local",
        "http://user:pass@adguard.local",
        "http://adguard.local?query=1",
        "http://adguard.local#fragment",
        "http://",
        "",
    ],
)
def test_parse_address_invalid(address: str) -> None:
    """Test invalid address formats are rejected."""
    with pytest.raises(ValueError):
        _parse_address(address)


@pytest.mark.parametrize(
    "address",
    [
        "ftp://adguard.local",
        "http://user:pass@adguard.local",
        "http://adguard.local?query=1",
        "http://adguard.local#fragment",
        "http://",
    ],
)
async def test_invalid_user_address(
    hass: HomeAssistant,
    address: str,
) -> None:
    """Test invalid address formats are rejected before connecting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: address,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_url"}


async def test_full_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test registering an integration and finishing flow works."""
    aioclient_mock.get(
        "http://127.0.0.1:3000/control/status",
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
    assert config_entry.title == "127.0.0.1"
    assert config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD],
        CONF_PATH: DEFAULT_BASE_PATH,
        CONF_PORT: 3000,
        CONF_SSL: False,
        CONF_USERNAME: FIXTURE_USER_INPUT[CONF_USERNAME],
        CONF_VERIFY_SSL: FIXTURE_USER_INPUT[CONF_VERIFY_SSL],
    }
    assert not config_entry.options


@pytest.mark.parametrize(
    ("user_url", "expected_host", "expected_port", "expected_path", "expected_ssl", "status_url"),
    [
        (
            "1.2.3.4",
            "1.2.3.4",
            3000,
            DEFAULT_BASE_PATH,
            False,
            "http://1.2.3.4:3000/control/status",
        ),
        (
            "1.2.3.4:3000",
            "1.2.3.4",
            3000,
            DEFAULT_BASE_PATH,
            False,
            "http://1.2.3.4:3000/control/status",
        ),
        (
            "http://adguard.local",
            "adguard.local",
            80,
            DEFAULT_BASE_PATH,
            False,
            "http://adguard.local:80/control/status",
        ),
        (
            "http://adguard.local:3000",
            "adguard.local",
            3000,
            DEFAULT_BASE_PATH,
            False,
            "http://adguard.local:3000/control/status",
        ),
        (
            "https://adguard.local",
            "adguard.local",
            443,
            DEFAULT_BASE_PATH,
            True,
            "https://adguard.local:443/control/status",
        ),
        (
            "https://adguard.local:9443",
            "adguard.local",
            9443,
            DEFAULT_BASE_PATH,
            True,
            "https://adguard.local:9443/control/status",
        ),
        (
            "https://sub.domain.tld/proxy/control",
            "sub.domain.tld",
            443,
            "/proxy/control",
            True,
            "https://sub.domain.tld:443/proxy/control/status",
        ),
        (
            "adguard.local/proxy/control",
            "adguard.local",
            3000,
            "/proxy/control",
            False,
            "http://adguard.local:3000/proxy/control/status",
        ),
    ],
)
async def test_user_flow_supported_url_formats(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    user_url: str,
    expected_host: str,
    expected_port: int,
    expected_path: str,
    expected_ssl: bool,
    status_url: str,
) -> None:
    """Test supported URL/address input formats through full user flow."""
    aioclient_mock.get(
        status_url,
        json={"version": "v0.99.0"},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: user_url,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == expected_host
    assert result["data"][CONF_PORT] == expected_port
    assert result["data"][CONF_PATH] == expected_path
    assert result["data"][CONF_SSL] is expected_ssl


async def test_full_url_with_path(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test full URL input with custom reverse proxy path."""
    aioclient_mock.get(
        "https://mock-adguard:443/proxy/control/status",
        json={"version": "v0.99.0"},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_URL: "https://mock-adguard/proxy/control",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "mock-adguard"
    assert result["data"] == {
        CONF_HOST: "mock-adguard",
        CONF_PASSWORD: "pass",
        CONF_PATH: "/proxy/control",
        CONF_PORT: 443,
        CONF_SSL: True,
        CONF_USERNAME: "user",
        CONF_VERIFY_SSL: True,
    }


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN, data={"host": "mock-adguard", "port": 3000}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={"url": "mock-adguard:3000", "verify_ssl": True},
        context={"source": config_entries.SOURCE_USER},
    )
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_hassio_already_configured(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN, data={"host": "mock-adguard", "port": 3000}
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
        CONF_PATH: DEFAULT_BASE_PATH,
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
