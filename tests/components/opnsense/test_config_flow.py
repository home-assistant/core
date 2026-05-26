"""Tests for the OPNsense config flow."""

from collections.abc import Iterable
from unittest.mock import AsyncMock, patch

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseConnectionError,
    OPNsenseInvalidAuth,
    OPNsenseInvalidURL,
    OPNsensePrivilegeMissing,
    OPNsenseTimeoutError,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.opnsense import OPNsenseSSLError, OPNsenseUnknownFirmware
from homeassistant.components.opnsense.const import CONF_TRACKER_INTERFACES, DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntry,
    ConfigSubentryData,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA, CONFIG_DATA_IMPORT

from tests.common import MockConfigEntry

# Constants for test values
TEST_URL = "http://router.lan/api"


async def test_interfaces_step_with_tracker_interfaces(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test interfaces step with tracker_interfaces in user_input (covering the missing branch)."""
    # Patch the client to return interfaces
    mock_opnsense_client.return_value.get_device_unique_id.return_value = (
        "unique_id_789"
    )
    mock_opnsense_client.return_value.get_interfaces.return_value = {
        "LAN": {"name": "LAN"},
        "WAN": {"name": "WAN"},
    }

    # Go through user step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**CONFIG_DATA, "verify_ssl": True},
    )
    # Now submit interfaces step with tracker_interfaces
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRACKER_INTERFACES: ["LAN", "WAN"]},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TRACKER_INTERFACES] == ["LAN", "WAN"]


async def test_import(hass: HomeAssistant, mock_opnsense_client: AsyncMock) -> None:
    """Test import step."""
    mock_opnsense_client.return_value.get_device_unique_id.return_value = (
        "unique_id_123"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA_IMPORT,
    )

    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result.get("title") == CONFIG_DATA_IMPORT[CONF_URL]


async def test_import_unique_id_already_configured(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test import step when unique ID is already configured (should abort)."""
    # The fixture patches config_flow and component clients separately.
    # Import uses the config_flow client default unique ID from setup_mock_opnsense_client.
    existing_unique_id = "mocked_unique_id"
    # First, create a config entry with the same unique ID
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_IMPORT,
        unique_id=existing_unique_id,
    )
    existing_entry.add_to_hass(hass)

    # Now attempt to import, which should abort due to duplicate unique ID
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA_IMPORT,
    )
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_user(hass: HomeAssistant, mock_opnsense_client: AsyncMock) -> None:
    """Test user config."""
    mock_opnsense_client.return_value.get_device_unique_id.return_value = (
        "unique_id_456"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Submit user step, should go to interfaces step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_DATA,
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "interfaces"

    # Submit interfaces step (simulate user selecting all interfaces)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRACKER_INTERFACES: []},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result.get("title") == CONFIG_DATA[CONF_URL]
    assert result.get("data") == CONFIG_DATA
    assert "result" in result
    config_entry: ConfigEntry | None = result.get("result")
    assert config_entry is not None
    subentries: Iterable[ConfigSubentryData] | None = result.get("subentries")
    assert subentries is not None
    assert subentries == ()


async def test_user_unique_id_already_configured(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test user flow aborts when unique ID is already configured."""
    existing_unique_id = "unique_id_already_configured"
    mock_opnsense_client.return_value.get_device_unique_id.return_value = (
        existing_unique_id
    )

    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        unique_id=existing_unique_id,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_DATA,
    )
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (OPNsenseInvalidAuth, "invalid_auth"),
        (OPNsensePrivilegeMissing, "privilege_missing"),
        (OPNsenseInvalidURL, "invalid_url"),
        (OPNsenseSSLError, "ssl_error"),
        (OPNsenseConnectionError, "cannot_connect"),
        (OPNsenseTimeoutError, "cannot_connect"),
        (OPNsenseUnknownFirmware, "unknown_version"),
        (OPNsenseBelowMinFirmware, "invalid_version"),
    ],
)
async def test_user_exceptions(
    hass: HomeAssistant,
    exc: type[Exception],
    expected: str,
) -> None:
    """Test all exception branches in async_step_user."""
    patch_target = (
        "homeassistant.components.opnsense.config_flow.OPNsenseClient.validate"
    )
    with patch(patch_target, side_effect=exc):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": expected}


async def test_interfaces_step_user_input_missing(
    hass: HomeAssistant,
) -> None:
    """Test interfaces step behavior via the flow manager."""
    with (
        patch("homeassistant.components.opnsense.config_flow.OPNsenseClient.validate"),
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient.get_device_unique_id",
            return_value=None,
        ),
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient.get_interfaces",
            return_value={"LAN": {"name": "LAN"}},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**CONFIG_DATA, CONF_URL: TEST_URL},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "interfaces"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        # Submitting an empty dict omits tracker_interfaces and creates the entry,
        # so no additional interfaces-step submission is needed.


async def test_import_exceptions(hass: HomeAssistant) -> None:
    """Test all exception branches in async_step_import."""
    import_data = dict(CONFIG_DATA_IMPORT)
    patch_target = (
        "homeassistant.components.opnsense.config_flow.OPNsenseClient.validate"
    )
    patch_interfaces = (
        "homeassistant.components.opnsense.config_flow.OPNsenseClient.get_interfaces"
    )
    exceptions = [
        (OPNsenseInvalidURL, "invalid_url"),
        (OPNsenseInvalidAuth, "invalid_auth"),
        (OPNsensePrivilegeMissing, "privilege_missing"),
        (OPNsenseSSLError, "ssl_error"),
        (OPNsenseConnectionError, "cannot_connect"),
        (OPNsenseTimeoutError, "cannot_connect"),
        (OPNsenseUnknownFirmware, "unknown_version"),
        (OPNsenseBelowMinFirmware, "invalid_version"),
        (Exception, "unknown"),
    ]
    for exc, reason in exceptions:
        with (
            patch(patch_target, side_effect=exc),
            patch(patch_interfaces),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=import_data,
            )
            assert result["type"] == data_entry_flow.FlowResultType.ABORT
            assert result["reason"] == reason


async def test_import_empty_tracker_interfaces(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test import with empty CONF_TRACKER_INTERFACES (should pop the key)."""
    import_data = dict(CONFIG_DATA_IMPORT)
    import_data[CONF_TRACKER_INTERFACES] = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=import_data,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert CONF_TRACKER_INTERFACES not in result["data"]


async def test_import_missing_interfaces(hass: HomeAssistant) -> None:
    """Test import with missing tracker interfaces (should create issue and abort)."""
    import_data = dict(CONFIG_DATA_IMPORT)
    import_data[CONF_TRACKER_INTERFACES] = ["MISSING"]
    with (
        patch("homeassistant.components.opnsense.config_flow.OPNsenseClient.validate"),
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient.get_interfaces",
            return_value={"LAN": {"name": "LAN"}},
        ),
        patch(
            "homeassistant.components.opnsense.config_flow.async_create_issue"
        ) as mock_issue,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=import_data,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "import_failed_missing_interfaces"
        mock_issue.assert_called()


async def test_abort_import_helper(hass: HomeAssistant) -> None:
    """Test import abort behavior creates an issue."""
    with (
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient.validate",
            side_effect=OPNsenseInvalidURL,
        ),
        patch(
            "homeassistant.components.opnsense.config_flow.async_create_issue"
        ) as mock_issue,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONFIG_DATA_IMPORT,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "invalid_url"
        mock_issue.assert_called()


async def test_on_unknown_error(hass: HomeAssistant) -> None:
    """Test when we have unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch(
        "homeassistant.components.opnsense.config_flow.OPNsenseClient.validate",
        side_effect=TypeError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("errors") == {"base": "unknown"}

    # No error this time
    with (
        patch("homeassistant.components.opnsense.config_flow.OPNsenseClient.validate"),
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient.get_interfaces",
            return_value={"LAN": {"name": "LAN"}},
        ),
    ):
        # Submit user step, should go to interfaces step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "interfaces"

        # Submit interfaces step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TRACKER_INTERFACES: []},
        )
        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
