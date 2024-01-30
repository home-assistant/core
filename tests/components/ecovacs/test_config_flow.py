"""Test Ecovacs config flow."""
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, Mock

from aiohttp import ClientError
from deebot_client.exceptions import InvalidAuthenticationError, MqttError
import pytest

from homeassistant.components.ecovacs.const import (
    CONF_CONTINENT,
    CONF_OVERRIDE_MQTT_URL,
    DOMAIN,
    InstanceMode,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_COUNTRY, CONF_MODE, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from .const import (
    IMPORT_DATA,
    VALID_ENTRY_DATA_CLOUD,
    VALID_ENTRY_DATA_SELF_HOSTED,
    VALID_ENTRY_DATA_SELF_HOSTED_WITH_VALIDATE_CERT,
)

from tests.common import MockConfigEntry

USER_STEP_SELF_HOSTED = {CONF_MODE: InstanceMode.SELF_HOSTED}


async def _test_user_flow(
    hass: HomeAssistant,
    *,
    user_input_auth: dict[str, Any],
    user_input_user: dict[str, Any] | None = None,
    show_advanced_options: bool = False,
) -> dict[str, Any]:
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": show_advanced_options},
    )

    if show_advanced_options:
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert not result["errors"]

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input_user or {},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input_auth,
    )


@pytest.mark.parametrize(
    ("show_advanced_options", "user_input_auth", "user_input_user"),
    [
        (True, VALID_ENTRY_DATA_CLOUD, None),
        (True, VALID_ENTRY_DATA_SELF_HOSTED, USER_STEP_SELF_HOSTED),
        (False, VALID_ENTRY_DATA_CLOUD, None),
    ],
    ids=["advanced_cloud", "advanced_self_hosted", "cloud"],
)
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
    *,
    show_advanced_options: bool,
    user_input_auth: dict[str, Any],
    user_input_user: dict[str, Any],
) -> None:
    """Test the user config flow."""
    result = await _test_user_flow(
        hass,
        user_input_auth=user_input_auth,
        user_input_user=user_input_user,
        show_advanced_options=show_advanced_options,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == user_input_auth[CONF_USERNAME]
    assert result["data"] == user_input_auth
    mock_setup_entry.assert_called()
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_called()


def _cannot_connect_error(user_input: dict[str, Any]) -> str:
    field = "base"
    if CONF_OVERRIDE_MQTT_URL in user_input:
        field = CONF_OVERRIDE_MQTT_URL

    return {field: "cannot_connect"}


@pytest.mark.parametrize(
    ("side_effect_mqtt", "errors_mqtt"),
    [
        (MqttError, _cannot_connect_error),
        (InvalidAuthenticationError, lambda _: {"base": "invalid_auth"}),
        (Exception, lambda _: {"base": "unknown"}),
    ],
    ids=["cannot_connect", "invalid_auth", "unknown"],
)
@pytest.mark.parametrize(
    ("side_effect_rest", "reason_rest"),
    [
        (ClientError, "cannot_connect"),
        (InvalidAuthenticationError, "invalid_auth"),
        (Exception, "unknown"),
    ],
    ids=["cannot_connect", "invalid_auth", "unknown"],
)
@pytest.mark.parametrize(
    ("show_advanced_options", "user_input_auth", "user_input_user", "entry_data"),
    [
        (True, VALID_ENTRY_DATA_CLOUD, None, None),
        (
            True,
            VALID_ENTRY_DATA_SELF_HOSTED,
            USER_STEP_SELF_HOSTED,
            VALID_ENTRY_DATA_SELF_HOSTED_WITH_VALIDATE_CERT,
        ),
        (False, VALID_ENTRY_DATA_CLOUD, None, None),
    ],
    ids=["advanced_cloud", "advanced_self_hosted", "cloud"],
)
async def test_user_flow_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
    side_effect_rest: Exception,
    reason_rest: str,
    side_effect_mqtt: Exception,
    errors_mqtt: Callable[[dict[str, Any]], str],
    show_advanced_options: bool,
    user_input_auth: dict[str, Any],
    user_input_user: dict[str, Any] | None,
    entry_data: dict[str, Any] | None,
) -> None:
    """Test handling invalid connection."""

    # Authenticator raises error
    mock_authenticator_authenticate.side_effect = side_effect_rest
    result = await _test_user_flow(
        hass,
        user_input_auth=user_input_auth,
        user_input_user=user_input_user,
        show_advanced_options=show_advanced_options,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": reason_rest}
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_not_called()
    mock_setup_entry.assert_not_called()

    mock_authenticator_authenticate.reset_mock(side_effect=True)

    # MQTT raises error
    mock_mqtt_client.verify_config.side_effect = side_effect_mqtt
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input_auth,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == errors_mqtt(user_input_auth)
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_called()
    mock_setup_entry.assert_not_called()

    mock_authenticator_authenticate.reset_mock(side_effect=True)
    mock_mqtt_client.verify_config.reset_mock(side_effect=True)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input_auth,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry_data = entry_data or user_input_auth
    assert result["title"] == entry_data[CONF_USERNAME]
    assert result["data"] == entry_data
    mock_setup_entry.assert_called()
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_called()


async def test_import_flow(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
) -> None:
    """Test importing yaml config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=IMPORT_DATA.copy(),
    )
    mock_authenticator_authenticate.assert_called()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == VALID_ENTRY_DATA_CLOUD[CONF_USERNAME]
    assert result["data"] == VALID_ENTRY_DATA_CLOUD
    assert (HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}") in issue_registry.issues
    mock_setup_entry.assert_called()
    mock_mqtt_client.verify_config.assert_called()


async def test_import_flow_already_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test importing yaml config where entry already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_ENTRY_DATA_CLOUD)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=IMPORT_DATA.copy(),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert (HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}") in issue_registry.issues


@pytest.mark.parametrize("show_advanced_options", [True, False])
@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (ClientError, "cannot_connect"),
        (InvalidAuthenticationError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_import_flow_error(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
    side_effect: Exception,
    reason: str,
    show_advanced_options: bool,
) -> None:
    """Test handling invalid connection."""
    mock_authenticator_authenticate.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_IMPORT,
            "show_advanced_options": show_advanced_options,
        },
        data=IMPORT_DATA.copy(),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == reason
    assert (
        DOMAIN,
        f"deprecated_yaml_import_issue_{reason}",
    ) in issue_registry.issues
    mock_authenticator_authenticate.assert_called()


@pytest.mark.parametrize("show_advanced_options", [True, False])
@pytest.mark.parametrize(
    ("reason", "user_input"),
    [
        ("invalid_country_length", IMPORT_DATA | {CONF_COUNTRY: "too_long"}),
        ("invalid_country_length", IMPORT_DATA | {CONF_COUNTRY: "a"}),  # too short
        ("invalid_continent_length", IMPORT_DATA | {CONF_CONTINENT: "too_long"}),
        ("invalid_continent_length", IMPORT_DATA | {CONF_CONTINENT: "a"}),  # too short
        ("continent_not_match", IMPORT_DATA | {CONF_CONTINENT: "AA"}),
    ],
)
async def test_import_flow_invalid_data(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    reason: str,
    user_input: dict[str, Any],
    show_advanced_options: bool,
) -> None:
    """Test handling invalid connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_IMPORT,
            "show_advanced_options": show_advanced_options,
        },
        data=user_input,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == reason
    assert (
        DOMAIN,
        f"deprecated_yaml_import_issue_{reason}",
    ) in issue_registry.issues
