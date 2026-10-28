"""Web-account settings submitted with V2 consent; all values are synthetic."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from yarl import URL

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.solaredge.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow as oauth

from .test_v2_runtime import BASE

V1_ENTRY = {
    "site_id": "123",
    "api_key": "synthetic-v1-key",
    "username": "synthetic-old-web",
    "password": "synthetic-old-password",
}
NEW_WEB = {"username": "synthetic-new-web", "password": "synthetic-new-password"}


@pytest.fixture
def web_login() -> Generator[MagicMock]:
    """Intercept the web-account check; valid unless a test sets a failure."""
    with patch(
        "homeassistant.components.solaredge.config_flow.SolarEdgeWeb"
    ) as web_class:
        web_class.return_value.async_get_equipment = AsyncMock()
        yield web_class


def _reject(web_login: MagicMock) -> None:
    web_login.return_value.async_get_equipment.side_effect = ClientResponseError(
        MagicMock(), (), status=401
    )


async def _register_implementation(hass: HomeAssistant) -> None:
    """Register synthetic application credentials and an HTTPS external URL."""
    hass.config.external_url = "https://ha.example.com"
    oauth.async_register_implementation(
        hass,
        "solaredge",
        await async_get_auth_implementation(
            hass, "solaredge", ClientCredential("synthetic-client", "synthetic-secret")
        ),
    )


async def _authorize(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    result: ConfigFlowResult,
    site: int = 123,
) -> ConfigFlowResult:
    """Pick the implementation, call the signed callback and finish the flow."""
    assert result["step_id"] == "pick_implementation"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "solaredge"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    aioclient_mock.post(
        BASE + "/oauth2/token",
        json={
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    )
    aioclient_mock.get(BASE + "/sites/123", json={"siteId": site})
    client = await hass_client()
    response = await client.get(
        "/auth/external/callback/solaredge",
        params={
            "external_id": URL(result["url"]).query["external_id"],
            "code": "synthetic-code",
        },
    )
    assert response.status == 200
    return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.usefixtures("recorder_mock", "mock_setup_entry")
async def test_new_v2_entry_keeps_validated_web_login(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    web_login: MagicMock,
) -> None:
    """Optional module-statistics login is validated first, saved after consent."""
    await _register_implementation(hass)
    result = await hass.config_entries.flow.async_init(
        "solaredge", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"site_id": "123", "use_oauth": True, "web_auth": NEW_WEB}
    )
    assert web_login.called
    assert web_login.call_args.kwargs["username"] == NEW_WEB["username"]
    assert web_login.call_args.kwargs["password"] == NEW_WEB["password"]
    assert not hass.config_entries.async_entries("solaredge")
    result = await _authorize(hass, hass_client, aioclient_mock, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data["api_version"] == 2
    assert entry.data["token"]["refresh_token"] == "synthetic-refresh"
    assert entry.data["username"] == NEW_WEB["username"]
    assert entry.data["password"] == NEW_WEB["password"]


@pytest.mark.usefixtures("recorder_mock")
async def test_new_v2_invalid_web_login_stays_on_form(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, web_login: MagicMock
) -> None:
    """Rejected web credentials never start consent or create anything."""
    await _register_implementation(hass)
    _reject(web_login)
    result = await hass.config_entries.flow.async_init(
        "solaredge", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"site_id": "123", "use_oauth": True, "web_auth": NEW_WEB}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
    assert aioclient_mock.call_count == 0
    assert not hass.config_entries.async_entries("solaredge")


@pytest.mark.usefixtures("recorder_mock", "mock_setup_entry")
@pytest.mark.parametrize(
    ("web", "site", "expected_web", "validated"),
    [
        pytest.param(NEW_WEB, 123, NEW_WEB, True, id="replaced"),
        pytest.param({"username": "", "password": ""}, 123, {}, False, id="cleared"),
        pytest.param(
            None,
            123,
            {"username": "synthetic-old-web", "password": "synthetic-old-password"},
            False,
            id="omitted",
        ),
        pytest.param(NEW_WEB, 999, None, True, id="authorization-aborted"),
    ],
)
async def test_v1_to_v2_reconfigure_applies_web_settings_after_consent(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    web_login: MagicMock,
    web: dict[str, str] | None,
    site: int,
    expected_web: dict[str, str] | None,
    validated: bool,
) -> None:
    """Pending web changes are committed only together with a successful grant."""
    await _register_implementation(hass)
    entry = MockConfigEntry(
        domain="solaredge", unique_id="synthetic-identity", data=deepcopy(V1_ENTRY)
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    submitted: dict = {"use_oauth": True}
    if web is not None:
        submitted["web_auth"] = web
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], submitted
    )
    assert web_login.called is validated
    assert entry.data == V1_ENTRY
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        result = await _authorize(hass, hass_client, aioclient_mock, result, site)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    if expected_web is None:
        assert result["reason"] == "invalid_site"
        assert entry.data == V1_ENTRY
        return
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "synthetic-identity"
    assert entry.data["api_version"] == 2
    assert "api_key" not in entry.data
    assert {
        key: entry.data[key] for key in ("username", "password") if key in entry.data
    } == expected_web


@pytest.mark.usefixtures("recorder_mock")
async def test_v1_to_v2_invalid_web_login_keeps_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, web_login: MagicMock
) -> None:
    """A rejected replacement stays on the form and changes nothing."""
    await _register_implementation(hass)
    _reject(web_login)
    entry = MockConfigEntry(domain="solaredge", data=deepcopy(V1_ENTRY))
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_oauth": True, "web_auth": NEW_WEB}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_auth"}
    assert aioclient_mock.call_count == 0
    assert entry.data == V1_ENTRY


@pytest.mark.usefixtures("recorder_mock", "mock_setup_entry")
async def test_duplicate_site_v2_entry_aborts_without_saving(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    web_login: MagicMock,
) -> None:
    """An already configured site is not duplicated and keeps its own settings."""
    await _register_implementation(hass)
    existing = MockConfigEntry(domain="solaredge", data=deepcopy(V1_ENTRY))
    existing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "solaredge", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"site_id": "123", "use_oauth": True, "web_auth": NEW_WEB}
    )
    result = await _authorize(hass, hass_client, aioclient_mock, result)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries("solaredge") == [existing]
    assert existing.data == V1_ENTRY
