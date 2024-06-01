"""Test the SMLIGHT SLZB config flow."""

from ipaddress import ip_address
from json import loads
from unittest.mock import AsyncMock, patch

from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError, SmlightError
from pysmlight.web import Info
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.smlight.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry, load_fixture

DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="SLZB-06.local.",
    name="mock_name",
    port=6638,
    properties={"mac": "AA:BB:CC:DD:EE:FF"},
    type="mock_type",
)

DISCOVERY_INFO_LEGACY = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="SLZB-06.local.",
    name="mock_name",
    port=6638,
    properties={},
    type="mock_type",
)


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full manual user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    mock_info = Info.from_dict(loads(load_fixture("smlight/info.json")))
    with (
        patch(
            "pysmlight.web.Api2.get_info",
            return_value=mock_info,
        ),
        patch(
            "pysmlight.web.Api2.check_auth_needed",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "slzb-06.local",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "SLZB-06p7"
    assert result["data"] == {
        CONF_HOST: "slzb-06.local",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the full zeroconf flow including authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result.get("description_placeholders") == {"host": "SLZB-06.local"}
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "confirm_discovery"

    mock_info = Info.from_dict(loads(load_fixture("smlight/info.json")))
    with (
        patch(
            "pysmlight.web.Api2.get_info",
            return_value=mock_info,
        ),
        patch(
            "pysmlight.web.Api2.check_auth_needed",
            return_value=True,
        ),
        patch(
            "pysmlight.web.Api2.authenticate",
        ),
    ):
        progress = hass.config_entries.flow.async_progress()
        assert len(progress) == 1
        assert progress[0].get("flow_id") == result["flow_id"]
        assert progress[0]["context"].get("confirm_only") is True

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result2.get("type") is FlowResultType.FORM
        assert result2.get("step_id") == "auth"

        progress2 = hass.config_entries.flow.async_progress()
        assert len(progress2) == 1
        assert progress2[0].get("flow_id") == result["flow_id"]

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test-user",
                CONF_PASSWORD: "test-pass",
            },
        )

        assert result3.get("type") is FlowResultType.CREATE_ENTRY
        assert result3 == snapshot

        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"


async def test_user_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort user flow if device already configured."""
    mock_info = Info.from_dict(loads(load_fixture("smlight/info.json")))
    with (
        patch(
            "pysmlight.web.Api2.get_info",
            return_value=mock_info,
        ),
        patch(
            "pysmlight.web.Api2.check_auth_needed",
            return_value=False,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_HOST: "slzb-06.lan",
            },
        )

        assert result.get("type") is FlowResultType.ABORT
        assert result.get("reason") == "already_configured"


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort zeroconf flow if device already configured."""
    mock_info = Info.from_dict(loads(load_fixture("smlight/info.json")))
    with (
        patch(
            "pysmlight.web.Api2.get_info",
            return_value=mock_info,
        ),
        patch(
            "pysmlight.web.Api2.check_auth_needed",
            return_value=False,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=DISCOVERY_INFO,
        )

        assert result.get("type") is FlowResultType.ABORT
        assert result.get("reason") == "already_configured"


async def test_user_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    with (
        patch(
            "pysmlight.web.Api2.check_auth_needed",
            return_value=True,
        ),
        patch(
            "pysmlight.web.Api2.authenticate",
            side_effect=SmlightAuthError,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_HOST: "slzb-06.local",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result.get("step_id") == "auth"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test",
                CONF_PASSWORD: "bad",
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}
        assert result2.get("step_id") == "auth"


async def test_user_api_exception(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle unknown exceptions in pysmlight api."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pysmlight.web.Api2.check_auth_needed",
        side_effect=SmlightError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "slzb-06.local",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
        assert result.get("step_id") == "user"


async def test_user_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle user cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pysmlight.web.Api2.check_auth_needed",
        side_effect=SmlightConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "slzb-06.local",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        assert result.get("step_id") == "user"


async def test_zeroconf_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle zeroconf cannot connect error."""
    with patch(
        "pysmlight.web.Api2.check_auth_needed",
        side_effect=SmlightConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=DISCOVERY_INFO,
        )
        assert result["type"] == FlowResultType.FORM
        assert result.get("step_id") == "confirm_discovery"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}
        assert result2.get("step_id") == "confirm_discovery"


async def test_zeroconf_legacy_mac(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we can get unique id MAC address for older firmwares."""
    mock_info = Info.from_dict(loads(load_fixture("smlight/info.json")))
    with (
        patch(
            "pysmlight.web.Api2.get_info",
            return_value=mock_info,
        ),
        patch(
            "pysmlight.web.Api2.check_auth_needed",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=DISCOVERY_INFO_LEGACY,
        )

        progress = hass.config_entries.flow.async_progress()
        assert len(progress) == 1
        assert "context" in progress[0]
        assert progress[0]["context"].get("unique_id") == format_mac(mock_info.MAC)
        assert progress[0].get("flow_id") == result["flow_id"]
        assert result.get("description_placeholders") == {"host": "SLZB-06.local"}


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow completes successfully."""
    mock_info = Info.from_dict(loads(load_fixture("smlight/info.json")))
    with (
        patch(
            "pysmlight.web.Api2.get_info",
            return_value=mock_info,
        ),
        patch(
            "pysmlight.web.Api2.check_auth_needed",
            return_value=True,
        ),
        patch(
            "pysmlight.web.Api2.authenticate",
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "reauth_confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-user",
                CONF_PASSWORD: "test-pass",
            },
        )

        assert result2.get("type") == FlowResultType.ABORT
        assert result2.get("reason") == "reauth_successful"


async def test_reauth_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow with error."""
    mock_info = Info.from_dict(loads(load_fixture("smlight/info.json")))
    with (
        patch(
            "pysmlight.web.Api2.get_info",
            return_value=mock_info,
        ),
        patch(
            "pysmlight.web.Api2.check_auth_needed",
            return_value=True,
        ),
        patch(
            "pysmlight.web.Api2.authenticate",
            side_effect=SmlightAuthError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "reauth_confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test",
                CONF_PASSWORD: "bad",
            },
        )

        assert result2.get("type") == FlowResultType.ABORT
        assert result2.get("reason") == "reauth_failed"
