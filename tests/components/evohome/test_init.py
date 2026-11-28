"""The tests for Evohome."""

from http import HTTPStatus
from typing import Any, Final
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import aiohttp
import evohomeasync2 as ec2
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.evohome.const import CONF_LOCATION_IDX, DOMAIN, EvoService
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import (
    get_evo_data,
    mock_config_entry,
    mock_evohome_api,
    mock_make_request,
    mock_post_request,
    setup_evohome,
)
from .const import USER_ID

EXC_BAD_CONNECTION = aiohttp.ClientConnectionError(
    "Connection error",
)


def _mock_response(status: HTTPStatus, body: dict | list) -> Mock:
    """Return a mock of a response from the vendor's server (JSON, a HTTP error)."""
    rsp = Mock(spec=aiohttp.ClientResponse, status=status, headers={})
    rsp.content_type = "application/json"
    rsp.json = AsyncMock(return_value=body)
    rsp.raise_for_status.side_effect = aiohttp.ClientResponseError(
        Mock(), (), status=status, message=status.phrase
    )
    return rsp


# the vendor's response to a bad username/password is not an exception (v2, then v1)
RSP_BAD_CREDENTIALS = Mock(
    return_value=_mock_response(HTTPStatus.BAD_REQUEST, {"error": "invalid_grant"})
)
RSP_BAD_CREDENTIALS_V1 = Mock(
    return_value=_mock_response(
        HTTPStatus.UNAUTHORIZED,
        [{"code": "EmailOrPasswordIncorrect", "message": "..."}],
    )
)
EXC_TOO_MANY_REQUESTS = aiohttp.ClientResponseError(
    Mock(),
    (),
    status=HTTPStatus.TOO_MANY_REQUESTS,
    message=HTTPStatus.TOO_MANY_REQUESTS.phrase,
)
EXC_BAD_GATEWAY = aiohttp.ClientResponseError(
    Mock(), (), status=HTTPStatus.BAD_GATEWAY, message=HTTPStatus.BAD_GATEWAY.phrase
)

SETUP_FAILURE_TESTS: Final = [
    pytest.param(
        EXC_BAD_CONNECTION,
        ConfigEntryState.SETUP_RETRY,
        "api_connection_failed",
        id="connection_failed",
    ),
    pytest.param(
        EXC_BAD_GATEWAY,
        ConfigEntryState.SETUP_RETRY,
        "api_server_error",
        id="bad_gateway",
    ),
    pytest.param(
        EXC_TOO_MANY_REQUESTS,
        ConfigEntryState.SETUP_RETRY,
        "api_rate_limited",
        id="too_many_requests",
    ),
]


@pytest.mark.parametrize(
    ("exception", "state", "translation_key"),
    [
        *SETUP_FAILURE_TESTS,
        pytest.param(
            RSP_BAD_CREDENTIALS,
            ConfigEntryState.SETUP_ERROR,
            "api_credentials_invalid",
            id="credentials_invalid",
        ),
    ],
)
async def test_authentication_failure_v2(
    hass: HomeAssistant,
    config: ConfigType,
    exception: Exception | Mock,
    state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test a failed authentication (v2 API) fails the setup, by its reason."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    with patch(
        "_evohome.credentials.CredentialsManagerBase._request",
        side_effect=exception,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is state
    assert entry.error_reason_translation_key == translation_key


@pytest.mark.parametrize(("exception", "state", "translation_key"), SETUP_FAILURE_TESTS)
async def test_client_request_failure_v2(
    hass: HomeAssistant,
    config: ConfigType,
    exception: Exception,
    state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test a failed request (v2 API) fails the setup, by its reason."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request("default"),
        ),
        patch("_evohome.auth.AbstractAuth._request", side_effect=exception),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is state
    assert entry.error_reason_translation_key == translation_key


async def test_bad_credentials_v1(
    hass: HomeAssistant,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test high-precision temps are disabled if the v1 API refuses the credentials."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    with (
        patch(
            "evohomeasync2.auth.AbstractTokenManager._post_access_token_request",
            mock_post_request("default"),
        ),
        patch(
            "_evohome.credentials.CredentialsManagerBase._request",
            side_effect=RSP_BAD_CREDENTIALS_V1,
        ),
        patch("_evohome.auth.AbstractAuth._make_request", mock_make_request("default")),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert get_evo_data(hass).account.client_v1 is None
    assert "The feature will be disabled until the next reload" in caplog.text


async def test_no_location_with_tcs(
    hass: HomeAssistant,
    config: ConfigType,
) -> None:
    """Test setup fails if no location of the account has a TCS."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    with (
        mock_evohome_api("default"),
        patch.object(ec2.Location, "tcs", new_callable=PropertyMock, return_value=None),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "no_systems"


async def test_location_first_refresh_failure(
    hass: HomeAssistant,
    config: ConfigType,
) -> None:
    """Test a failed first refresh of a location is retried, by its reason."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    with (
        mock_evohome_api("default"),
        patch.object(
            ec2.Location,
            "get_status",
            side_effect=ec2.ApiCallFailedError("API call failed"),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == "api_request_failed"


async def test_services_registered_if_setup_fails(
    hass: HomeAssistant,
    config: ConfigType,
) -> None:
    """Test the actions are registered even if setup fails."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    with patch.object(
        ec2.EvohomeClient, "setup", side_effect=ec2.ApiCallFailedError("API failed")
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert set(hass.services.async_services_for_domain(DOMAIN)) == set(EvoService)


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
async def test_setup(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test services after setup of evohome.

    Registered services vary by the type of system.
    """

    assert hass.services.async_services_for_domain(DOMAIN).keys() == snapshot


@pytest.mark.parametrize("install", ["sys_004", "sys_006"])
@pytest.mark.usefixtures("evohome")
async def test_setup_multiple_locations(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test every location of an account that has a TCS is set up."""

    evo = get_evo_data(hass)
    assert [c.loc.id for c in evo.locations] == [
        loc.id for loc in evo.account.client.locations if loc.tcs
    ]

    assert sorted(hass.states.async_entity_ids()) == snapshot


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
async def test_unload_and_remove(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test an entry can be unloaded, and its token cache is removed with it."""

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert DOMAIN in hass_storage

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN not in hass_storage


async def _async_setup_yaml(
    hass: HomeAssistant, config: ConfigType, install: str = "default"
) -> None:
    """Set up evohome from YAML (i.e. import it), with a mocked vendor's API."""

    with mock_evohome_api(install):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()


async def test_import_yaml(
    hass: HomeAssistant,
    config: ConfigType,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the YAML configuration is imported, and is flagged as deprecated."""

    await _async_setup_yaml(hass, config)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data == config
    assert entries[0].unique_id == USER_ID

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.7.0"
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_options") is None


async def test_import_yaml_already_configured(
    hass: HomeAssistant,
    config: ConfigType,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the YAML configuration is not imported again, but is still deprecated."""

    mock_config_entry(config).add_to_hass(hass)

    await _async_setup_yaml(hass, config)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({CONF_LOCATION_IDX: 1}, id="location_idx"),
        pytest.param({CONF_SCAN_INTERVAL: 600}, id="scan_interval"),
    ],
)
async def test_import_yaml_options_ignored(
    hass: HomeAssistant,
    config: ConfigType,
    options: ConfigType,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the YAML options that are no longer used are dropped, with an issue."""

    await _async_setup_yaml(hass, config | options)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].data == config
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_options")


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(
            ec2.BadUserCredentialsError("Bad credentials"),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            ec2.ApiConnectionFailedError("Connection failed"),
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(ValueError("Unexpected"), "unknown", id="unknown"),
    ],
)
async def test_import_yaml_failed(
    hass: HomeAssistant,
    config: ConfigType,
    exception: Exception,
    reason: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed import of the YAML configuration raises an issue, by its reason."""

    with patch.object(ec2.EvohomeClient, "setup", side_effect=exception):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


_STALE_ISSUES = {  # issue_id: translation_key
    "deprecated_clear_zone_override_service": "deprecated_clear_zone_override_service",
    "deprecated_preset_reset": "deprecated_preset_reset",
    "deprecated_refresh_system_service": "deprecated_refresh_system_service",
    "deprecated_reset_system_service": "deprecated_reset_system_service",
    "deprecated_set_system_mode_service": "deprecated_controller_service",
}


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [
            f"component.evohome.issues.{translation_key}.{key}"
            for translation_key in _STALE_ISSUES.values()
            for key in ("title", "description")
        ]
    ],
)
async def test_stale_deprecation_issues_removed(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test persistent repair issues of completed deprecations are removed."""

    for issue_id, translation_key in _STALE_ISSUES.items():
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=translation_key,
        )
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    async for _ in setup_evohome(hass, config, install=install):
        pass

    for issue_id in _STALE_ISSUES:
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
