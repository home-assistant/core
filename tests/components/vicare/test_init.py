"""Test ViCare initialization and migration."""

from unittest.mock import Mock, patch

from aiohttp import ClientError
import pytest
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)

from homeassistant.components.vicare.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from . import MODULE
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_v1_1_to_v2_1(hass: HomeAssistant) -> None:
    """Test migration of config entry from v1.1 through to v2.1."""
    mock_token = {
        "access_token": "mock-access-token",
        "refresh_token": "mock-refresh-token",
        "expires_at": 9999999999.0,
        "token_type": "Bearer",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
            "heating_type": "auto",
        },
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    with patch(
        f"{MODULE}.obtain_token_via_basic_auth_pkce",
        return_value=mock_token,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert "heating_type" not in config_entry.data
    assert "username" not in config_entry.data
    assert "password" not in config_entry.data
    assert "client_id" not in config_entry.data
    assert config_entry.data["auth_implementation"] == DOMAIN
    assert config_entry.data["token"]["refresh_token"] == "mock-refresh-token"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_v1_2_to_v2_1(hass: HomeAssistant) -> None:
    """Test migration of config entry from v1.2 to v2.1."""
    mock_token = {
        "access_token": "mock-access-token",
        "refresh_token": "mock-refresh-token",
        "expires_at": 9999999999.0,
        "token_type": "Bearer",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        f"{MODULE}.obtain_token_via_basic_auth_pkce",
        return_value=mock_token,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert "username" not in config_entry.data
    assert "password" not in config_entry.data
    assert "client_id" not in config_entry.data
    assert config_entry.data["auth_implementation"] == DOMAIN
    assert config_entry.data["token"]["refresh_token"] == "mock-refresh-token"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_token_failure(hass: HomeAssistant) -> None:
    """Test migration completes even when token cannot be obtained."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        f"{MODULE}.obtain_token_via_basic_auth_pkce",
        return_value={},
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert "username" not in config_entry.data
    assert "password" not in config_entry.data
    assert "client_id" not in config_entry.data
    assert config_entry.data["auth_implementation"] == DOMAIN
    assert config_entry.data["token"] == {}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_creates_repair_issue(hass: HomeAssistant) -> None:
    """Test migration creates a repair issue for redirect URI update."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        f"{MODULE}.obtain_token_via_basic_auth_pkce",
        return_value={
            "access_token": "a",
            "refresh_token": "r",
            "expires_at": 9999999999.0,
            "token_type": "Bearer",
        },
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "update_redirect_uri")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_v1_3_stamp_bump(hass: HomeAssistant) -> None:
    """Test pre-merge v1.3 entries are promoted to v2.1 without re-running migration."""
    token = {
        "access_token": "a",
        "refresh_token": "r",
        "expires_at": 9999999999.0,
        "token_type": "Bearer",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={"auth_implementation": DOMAIN, "token": token},
        version=1,
        minor_version=3,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.data["auth_implementation"] == DOMAIN
    assert config_entry.data["token"] == token


async def test_setup_entry_token_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed on invalid token."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=KeyError("token"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_implementation_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed when OAuth2 implementation is missing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        side_effect=ValueError("Implementation not available"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_token_refresh_transient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryNotReady on transient token refresh error."""
    mock_config_entry.add_to_hass(hass)

    request_info = Mock()
    request_info.real_url = "https://example.com"
    transient = OAuth2TokenRequestTransientError(
        domain=DOMAIN, request_info=request_info, status=503
    )
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=transient,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_token_refresh_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed when token refresh requires re-auth."""
    mock_config_entry.add_to_hass(hass)

    request_info = Mock()
    request_info.real_url = "https://example.com"
    reauth = OAuth2TokenRequestReauthError(
        domain=DOMAIN, request_info=request_info, status=401
    )
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=reauth,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_transient_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryNotReady on transient auth error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientError("connection failed"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_invalid_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed on PyViCare credentials error."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            side_effect=PyViCareInvalidCredentialsError,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_invalid_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed on PyViCare config error."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            side_effect=PyViCareInvalidConfigurationError,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


# Device migration test can be removed in 2025.4.0
async def test_device_and_entity_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the device registry is updated correctly."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
        Fixture({"type:boiler"}, "vicare/dummy-device-no-serial.json"),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.CLIMATE]),
    ):
        mock_config_entry.add_to_hass(hass)

        # device with serial data point
        device0 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={
                (DOMAIN, "gateway0"),
            },
            model="model0",
        )
        entry0 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway0-0",
            translation_key="heating",
            device_id=device0.id,
        )
        entry1 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway0_deviceSerialVitodens300W-heating-1",
            translation_key="heating",
            device_id=device0.id,
        )
        # device without serial data point
        device1 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={
                (DOMAIN, "gateway1"),
            },
            model="model1",
        )
        entry2 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway1-0",
            translation_key="heating",
            device_id=device1.id,
        )
        # device is not provided by api
        device2 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={
                (DOMAIN, "gateway2"),
            },
            model="model2",
        )
        entry3 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway2-0",
            translation_key="heating",
            device_id=device2.id,
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entry0.entity_id).unique_id
        == "gateway0_deviceSerialVitodens300W-heating-0"
    )
    assert (
        entity_registry.async_get(entry1.entity_id).unique_id
        == "gateway0_deviceSerialVitodens300W-heating-1"
    )
    assert (
        entity_registry.async_get(entry2.entity_id).unique_id
        == "gateway1_deviceId1-heating-0"
    )
    assert entity_registry.async_get(entry3.entity_id).unique_id == "gateway2-0"
