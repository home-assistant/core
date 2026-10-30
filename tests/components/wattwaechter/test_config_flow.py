"""Tests for the WattWächter config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from aio_wattwaechter import (
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
)
from aio_wattwaechter.models import _parse_system_info
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture

from homeassistant.components.wattwaechter.const import CONF_FW_VERSION, DOMAIN
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryDisabler,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import (
    MOCK_CONFIG_DATA,
    MOCK_DEVICE_ID,
    MOCK_DEVICE_NAME,
    MOCK_FW_VERSION,
    MOCK_HOST,
    MOCK_MAC,
    MOCK_MODEL,
    MOCK_SYSTEM_INFO_GAS,
    MOCK_TOKEN,
)

MOCK_ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(MOCK_HOST),
    ip_addresses=[ip_address(MOCK_HOST)],
    hostname="wattwaechter.local.",
    port=80,
    type="_wattwaechter._tcp.local.",
    name=f"WWP-{MOCK_DEVICE_ID}._wattwaechter._tcp.local.",
    properties={
        "id": f"WWP-{MOCK_DEVICE_ID}",
        "model": MOCK_MODEL,
        "ver": MOCK_FW_VERSION,
        "mac": MOCK_MAC,
    },
)


async def test_user_flow_success(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful manual configuration without auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: None,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_MODEL: "ww_plus",
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_auth_required(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow redirects to auth step when device requires a token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # system_info raises auth error → redirect to auth step
    mock_client.system_info.side_effect = WattwaechterAuthenticationError(
        "Auth required"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    # Submit token → success
    mock_client.system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: MOCK_TOKEN,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_MODEL: "ww_plus",
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow recovers after a connection failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_client.system_info.side_effect = WattwaechterConnectionError(
        "Connection refused"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"

    # Retry succeeds once the device is reachable again
    mock_client.system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when device is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (WattwaechterAuthenticationError("Invalid token"), "invalid_auth"),
        (WattwaechterConnectionError("Connection lost"), "cannot_connect"),
    ],
)
async def test_auth_step_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test auth step recovers after invalid token or connection failure."""
    # Trigger auth step via user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_client.system_info.side_effect = WattwaechterAuthenticationError(
        "Auth required"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )
    assert result["step_id"] == "auth"

    # Submit token with error
    mock_client.system_info.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "bad-token"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"]["base"] == expected_error

    # Retry with a working token succeeds
    mock_client.system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow_no_token_needed(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test zeroconf discovery when device doesn't require a token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: None,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_MODEL: "ww_plus",
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow_token_required(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test zeroconf discovery when device requires a token."""
    mock_client.system_info.side_effect = WattwaechterAuthenticationError(
        "Auth required"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    # Submit token → success
    mock_client.system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: MOCK_TOKEN,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_MODEL: "ww_plus",
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (WattwaechterAuthenticationError("Invalid token"), "invalid_auth"),
        (WattwaechterConnectionError("Connection lost"), "cannot_connect"),
    ],
)
async def test_zeroconf_auth_step_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test auth step recovers after errors when reached via zeroconf discovery."""
    # Trigger auth step via zeroconf discovery
    mock_client.system_info.side_effect = WattwaechterAuthenticationError(
        "Auth required"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )
    assert result["step_id"] == "auth"

    # Submit token with error
    mock_client.system_info.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "bad-token"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"]["base"] == expected_error

    # Retry with a working token succeeds
    mock_client.system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow_cannot_connect(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test zeroconf aborts when device is unreachable."""
    mock_client.system_info.side_effect = WattwaechterConnectionError(
        "Connection refused"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf aborts and updates the stored host when the IP has changed."""
    new_host = "192.168.1.200"
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(new_host),
        ip_addresses=[ip_address(new_host)],
        hostname="wattwaechter.local.",
        port=80,
        type="_wattwaechter._tcp.local.",
        name=f"WWP-{MOCK_DEVICE_ID}._wattwaechter._tcp.local.",
        properties={
            "id": f"WWP-{MOCK_DEVICE_ID}",
            "model": MOCK_MODEL,
            "ver": MOCK_FW_VERSION,
            "mac": MOCK_MAC,
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == new_host


async def test_zeroconf_flow_device_name_fetch_fails(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test zeroconf uses fallback title when device_name fetch fails."""
    mock_client.settings.side_effect = WattwaechterConnectionError("Connection lost")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"WattWächter {MOCK_DEVICE_ID[-4:]}"
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: None,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_MODEL: "ww_plus",
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication updates the stored token."""
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "new-token"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (WattwaechterAuthenticationError("Invalid token"), "invalid_auth"),
        (WattwaechterConnectionError("Connection lost"), "cannot_connect"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauth recovers after an invalid token or connection failure."""
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    mock_client.system_info.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "bad-token"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == expected_error

    # Retry with a working token succeeds
    mock_client.system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == MOCK_TOKEN


async def test_reauth_flow_wrong_device(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth aborts when the host now points to a different device."""
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    # Device reports a different esp_id than the one stored in the entry
    mock_client.system_info.return_value = MagicMock(
        **{"get_value.return_value": "WRONG-DEVICE"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert mock_config_entry.data[CONF_TOKEN] == MOCK_TOKEN


async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring the host updates the entry and keeps the token."""
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_host = "192.168.1.222"
    # The token field is pre-filled with the stored token and submitted as-is
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host, CONF_TOKEN: MOCK_TOKEN}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == new_host
    assert mock_config_entry.data[CONF_TOKEN] == MOCK_TOKEN


async def test_reconfigure_flow_clear_token(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test clearing the token field stores None instead of an empty string."""
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST, CONF_TOKEN: ""}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_TOKEN] is None


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (WattwaechterAuthenticationError("Invalid token"), "invalid_auth"),
        (WattwaechterConnectionError("Connection lost"), "cannot_connect"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reconfigure recovers after an invalid token or connection failure."""
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    mock_client.system_info.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"]["base"] == expected_error

    # Retry succeeds once the device is reachable again
    mock_client.system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_wrong_device(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure aborts when the host points to a different device."""
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    mock_client.system_info.return_value = MagicMock(
        **{"get_value.return_value": "WRONG-DEVICE"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.222"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert mock_config_entry.data[CONF_HOST] == MOCK_HOST


def _zeroconf_discovery(
    properties: dict[str, str], host: str = MOCK_HOST
) -> ZeroconfServiceInfo:
    """Return a zeroconf discovery with the given TXT records."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        hostname="wattwaechter.local.",
        port=80,
        type="_wattwaechter._tcp.local.",
        name=f"{properties.get('id', 'WW')}._wattwaechter._tcp.local.",
        properties=properties,
    )


@pytest.mark.parametrize(
    ("properties", "expected_unique_id"),
    [
        pytest.param(
            {"id": f"WWP-{MOCK_DEVICE_ID}", "model": "WW-Plus"},
            MOCK_DEVICE_ID,
            id="plus",
        ),
        pytest.param(
            {"id": f"WWGW-{MOCK_DEVICE_ID}", "model": "WW-GW-MF"},
            MOCK_DEVICE_ID,
            id="gw_mf",
        ),
        pytest.param(
            {"id": f"WWGW-{MOCK_DEVICE_ID}", "model": "WW-GW-ID"},
            MOCK_DEVICE_ID,
            id="gw_id",
        ),
        pytest.param(
            {"mac": "9b:fe:ff:45:3a:b4"},
            "9BFEFF453AB4",
            id="mac_fallback",
        ),
    ],
)
async def test_zeroconf_unique_id_is_bare_mac(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    properties: dict[str, str],
    expected_unique_id: str,
) -> None:
    """Test the unique ID strips the product prefix for all products."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_discovery(properties),
    )
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == expected_unique_id
    assert result["data"][CONF_DEVICE_ID] == expected_unique_id


async def test_zeroconf_gw_already_configured_by_user_flow(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a GW discovery matches the entry created from the system info esp_id."""
    new_host = "192.168.1.201"
    discovery = _zeroconf_discovery({"id": f"WWGW-{MOCK_DEVICE_ID}"}, new_host)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == new_host


@pytest.mark.parametrize(
    ("source", "disabled_by"),
    [
        (SOURCE_IGNORE, None),
        (SOURCE_USER, ConfigEntryDisabler.USER),
    ],
    ids=["ignored", "disabled"],
)
async def test_zeroconf_gw_matches_unmigrated_legacy_entry(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    source: str,
    disabled_by: ConfigEntryDisabler | None,
) -> None:
    """Test discovery matches an entry that kept its WWGW-<MAC> unique ID.

    Ignored and disabled entries are not set up, so they are not migrated.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG_DATA, CONF_DEVICE_ID: f"WWGW-{MOCK_DEVICE_ID}"},
        unique_id=f"WWGW-{MOCK_DEVICE_ID}",
        source=source,
        disabled_by=disabled_by,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_discovery({"id": f"WWGW-{MOCK_DEVICE_ID}"}),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_gw_model_from_system_info(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test a gas/water device stores the model ID and shows its product name."""
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_GAS

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_discovery(
            {
                "id": f"WWGW-{MOCK_DEVICE_ID}",
                "model": "WW-GW-MF",
                "ver": MOCK_FW_VERSION,
                "mac": MOCK_MAC,
            }
        ),
    )
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["model"] == "WattWächter Gas"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"][CONF_MODEL] == "ww_gw_mf"


async def test_user_flow_legacy_firmware_without_model_id(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test firmware without model_id is stored as a WattWächter Plus."""
    legacy = await async_load_json_object_fixture(hass, "system_info.json", DOMAIN)
    legacy["esp"] = [
        entry
        for entry in legacy["esp"]
        if entry["name"] not in ("model_id", "product_name")
    ]
    mock_client.system_info.return_value = _parse_system_info(legacy)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"][CONF_MODEL] == "ww_plus"
