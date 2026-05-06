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
from homeassistant.components.opnsense import (
    OPNsenseSSLError,
    OPNsenseUnknownFirmware,
    config_flow,
)
from homeassistant.components.opnsense.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntry,
    ConfigSubentryData,
)
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA, CONFIG_DATA_IMPORT

from tests.common import MockConfigEntry


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
    assert result.get("title") == "http://router.lan/api"


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
        user_input={"tracker_interfaces": []},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result.get("title") == "http://router.lan/api"
    assert result.get("data") == CONFIG_DATA
    assert "result" in result
    config_entry: ConfigEntry | None = result.get("result")
    assert config_entry is not None
    subentries: Iterable[ConfigSubentryData] | None = result.get("subentries")
    assert subentries is not None
    assert subentries == ()


async def test_abort_if_already_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if component is already setup."""

    # Pretend we already set up a config entry.
    hass.config.components.add(DOMAIN)
    mock_config_entry.add_to_hass(hass)

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


async def test_abort_import_if_already_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if component is already setup."""

    # Pretend we already set up a config entry.
    hass.config.components.add(DOMAIN)
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA,
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
        ((OPNsenseConnectionError, OPNsenseTimeoutError), "cannot_connect"),
        (OPNsenseUnknownFirmware, "unknown_version"),
        (OPNsenseBelowMinFirmware, "invalid_version"),
    ],
)
async def test_user_exceptions(hass: HomeAssistant, exc, expected) -> None:
    """Test all exception branches in async_step_user."""
    patch_target = (
        "homeassistant.components.opnsense.config_flow.OPNsenseClient.validate"
    )
    if isinstance(exc, tuple):
        # Patch to raise the first exception in the tuple
        exc_to_raise = exc[0]
    else:
        exc_to_raise = exc
    with patch(patch_target, side_effect=exc_to_raise):
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
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Test async_step_interfaces when _step_user_input is not a dict or missing CONF_URL."""
    flow = config_flow.OPNsenseConfigFlow()
    flow.hass = hass
    flow._step_user_input = None  # Not a dict
    result = await flow.async_step_interfaces(user_input={"tracker_interfaces": []})
    assert result["step_id"] == "user"
    flow._step_user_input = {}
    result = await flow.async_step_interfaces(user_input={"tracker_interfaces": []})
    assert result["step_id"] == "user"


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
        ((OPNsenseConnectionError, OPNsenseTimeoutError), "cannot_connect"),
        (OPNsenseUnknownFirmware, "invalid_version"),
        (OPNsenseBelowMinFirmware, "invalid_version"),
        (Exception, "unknown"),
    ]
    for exc, reason in exceptions:
        with (
            patch(
                patch_target, side_effect=exc if not isinstance(exc, tuple) else exc[0]
            ),
            patch(patch_interfaces),
        ):
            flow = config_flow.OPNsenseConfigFlow()
            flow.hass = hass
            result = await flow.async_step_import(import_data)
            assert result["type"] == data_entry_flow.FlowResultType.ABORT
            assert result["reason"] == reason


async def test_import_empty_tracker_interfaces(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test import with empty CONF_TRACKER_INTERFACES (should pop the key)."""
    import_data = dict(CONFIG_DATA_IMPORT)
    import_data["tracker_interfaces"] = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=import_data,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert "tracker_interfaces" not in result["data"]


async def test_import_missing_interfaces(hass: HomeAssistant) -> None:
    """Test import with missing tracker interfaces (should create issue and abort)."""
    import_data = dict(CONFIG_DATA_IMPORT)
    import_data["tracker_interfaces"] = ["MISSING"]
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
        flow = config_flow.OPNsenseConfigFlow()
        flow.hass = hass
        result = await flow.async_step_import(import_data)
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "import_failed_missing_interfaces"
        mock_issue.assert_called()


async def test_abort_import_helper(hass: HomeAssistant) -> None:
    """Test the _abort_import helper method directly."""
    flow = config_flow.OPNsenseConfigFlow()
    flow.hass = hass
    with patch(
        "homeassistant.components.opnsense.config_flow.async_create_issue"
    ) as mock_issue:
        result = flow._abort_import("invalid_url", "http://router.lan/api")
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
            user_input={"tracker_interfaces": []},
        )
        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
