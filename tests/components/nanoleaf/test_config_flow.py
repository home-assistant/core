"""Test the Nanoleaf config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, patch

from aionanoleaf import InvalidToken, Unauthorized, Unavailable
import pytest

from homeassistant import config_entries
from homeassistant.components import ssdp, zeroconf
from homeassistant.components.nanoleaf.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_NAME = "Canvas ADF9"
TEST_HOST = "192.168.0.100"
TEST_OTHER_HOST = "192.168.0.200"
TEST_TOKEN = "R34F1c92FNv3pcZs4di17RxGqiLSwHM"
TEST_OTHER_TOKEN = "Qs4dxGcHR34l29RF1c92FgiLQBt3pcM"
TEST_DEVICE_ID = "5E:2E:EA:XX:XX:XX"
TEST_OTHER_DEVICE_ID = "5E:2E:EA:YY:YY:YY"


def _mock_nanoleaf(
    host: str = TEST_HOST,
    auth_token: str = TEST_TOKEN,
    authorize_error: Exception | None = None,
    get_info_error: Exception | None = None,
):
    nanoleaf = MagicMock()
    nanoleaf.name = TEST_NAME
    nanoleaf.host = host
    nanoleaf.auth_token = auth_token
    nanoleaf.authorize = AsyncMock(side_effect=authorize_error)
    nanoleaf.get_info = AsyncMock(side_effect=get_info_error)
    return nanoleaf


async def test_user_unavailable_user_step_link_step(hass: HomeAssistant) -> None:
    """Test we handle Unavailable in user and link step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=Unavailable,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}
    assert not result2["last_step"]

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "link"

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=Unavailable,
    ):
        result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (Unavailable, "cannot_connect"),
        (InvalidToken, "invalid_token"),
        (Exception, "unknown"),
    ],
)
async def test_user_error_setup_finish(
    hass: HomeAssistant, error: Exception, reason: str
) -> None:
    """Test abort flow if on error in setup_finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "link"

    with (
        patch(
            "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        ),
        patch(
            "homeassistant.components.nanoleaf.config_flow.Nanoleaf.get_info",
            side_effect=error,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == reason


async def test_user_not_authorizing_new_tokens_user_step_link_step(
    hass: HomeAssistant,
) -> None:
    """Test we handle NotAuthorizingNewTokens in user step and link step."""
    with (
        patch(
            "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
            return_value=_mock_nanoleaf(authorize_error=Unauthorized()),
        ) as mock_nanoleaf,
        patch(
            "homeassistant.components.nanoleaf.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is None
        assert result["step_id"] == "user"
        assert not result["last_step"]

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] is None
        assert result2["step_id"] == "link"

        result3 = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"] is None
        assert result3["step_id"] == "link"

        result4 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result4["type"] is FlowResultType.FORM
        assert result4["errors"] == {"base": "not_allowing_new_tokens"}
        assert result4["step_id"] == "link"

        mock_nanoleaf.return_value.authorize.side_effect = None

        result5 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result5["type"] is FlowResultType.CREATE_ENTRY
        assert result5["title"] == TEST_NAME
        assert result5["data"] == {
            CONF_HOST: TEST_HOST,
            CONF_TOKEN: TEST_TOKEN,
        }
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_exception_user_step(hass: HomeAssistant) -> None:
    """Test we handle Exception errors in user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
        return_value=_mock_nanoleaf(authorize_error=Exception()),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}
    assert not result2["last_step"]

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
        return_value=_mock_nanoleaf(),
    ) as mock_nanoleaf:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
        assert result3["step_id"] == "link"

        mock_nanoleaf.return_value.authorize.side_effect = Exception()

        result4 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result4["type"] is FlowResultType.FORM
        assert result4["step_id"] == "link"
        assert result4["errors"] == {"base": "unknown"}

        mock_nanoleaf.return_value.authorize.side_effect = None
        mock_nanoleaf.return_value.get_info.side_effect = Exception()
        result5 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result5["type"] is FlowResultType.ABORT
    assert result5["reason"] == "unknown"


@pytest.mark.parametrize(
    ("source", "type_in_discovery_info"),
    [
        (config_entries.SOURCE_HOMEKIT, "_hap._tcp.local"),
        (config_entries.SOURCE_ZEROCONF, "_nanoleafms._tcp.local"),
        (config_entries.SOURCE_ZEROCONF, "_nanoleafapi._tcp.local."),
    ],
)
async def test_discovery_link_unavailable(
    hass: HomeAssistant, source: type, type_in_discovery_info: str
) -> None:
    """Test discovery and abort if device is unavailable."""
    with (
        patch(
            "homeassistant.components.nanoleaf.config_flow.Nanoleaf.get_info",
        ),
        patch(
            "homeassistant.components.nanoleaf.config_flow.load_json_object",
            return_value={},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address(TEST_HOST),
                ip_addresses=[ip_address(TEST_HOST)],
                hostname="mock_hostname",
                name=f"{TEST_NAME}.{type_in_discovery_info}",
                port=None,
                properties={zeroconf.ATTR_PROPERTIES_ID: TEST_DEVICE_ID},
                type=type_in_discovery_info,
            ),
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"] == {"name": TEST_NAME}
    assert context["unique_id"] == TEST_NAME

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=Unavailable,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_reauth(hass: HomeAssistant) -> None:
    """Test Nanoleaf reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_NAME,
        data={CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_OTHER_TOKEN},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
            return_value=_mock_nanoleaf(),
        ),
        patch(
            "homeassistant.components.nanoleaf.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
            },
            data=entry.data,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "link"

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    assert entry.data[CONF_HOST] == TEST_HOST
    assert entry.data[CONF_TOKEN] == TEST_TOKEN


@pytest.mark.parametrize(
    ("source", "type_in_discovery"),
    [
        (config_entries.SOURCE_HOMEKIT, "_hap._tcp.local"),
        (config_entries.SOURCE_ZEROCONF, "_nanoleafms._tcp.local"),
        (config_entries.SOURCE_ZEROCONF, "_nanoleafapi._tcp.local"),
    ],
)
@pytest.mark.parametrize(
    ("nanoleaf_conf_file", "remove_config"),
    [
        ({TEST_DEVICE_ID: {"token": TEST_TOKEN}}, True),
        ({TEST_HOST: {"token": TEST_TOKEN}}, True),
        (
            {
                TEST_DEVICE_ID: {"token": TEST_TOKEN},
                TEST_HOST: {"token": TEST_OTHER_TOKEN},
            },
            True,
        ),
        (
            {
                TEST_DEVICE_ID: {"token": TEST_TOKEN},
                TEST_OTHER_HOST: {"token": TEST_OTHER_TOKEN},
            },
            False,
        ),
        (
            {
                TEST_OTHER_DEVICE_ID: {"token": TEST_OTHER_TOKEN},
                TEST_HOST: {"token": TEST_TOKEN},
            },
            False,
        ),
    ],
)
async def test_import_discovery_integration(
    hass: HomeAssistant,
    source: str,
    type_in_discovery: str,
    nanoleaf_conf_file: dict[str, dict[str, str]],
    remove_config: bool,
) -> None:
    """Test discovery integration import.

    Test with different discovery flow sources and corresponding types.
    Test with different .nanoleaf_conf files with device_id (>= 2021.4), host (< 2021.4) and combination.
    Test removing the .nanoleaf_conf file if it was the only device in the file.
    Test updating the .nanoleaf_conf file if it was not the only device in the file.
    """
    with (
        patch(
            "homeassistant.components.nanoleaf.config_flow.load_json_object",
            return_value=dict(nanoleaf_conf_file),
        ),
        patch(
            "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
            return_value=_mock_nanoleaf(TEST_HOST, TEST_TOKEN),
        ),
        patch(
            "homeassistant.components.nanoleaf.config_flow.save_json",
            return_value=None,
        ) as mock_save_json,
        patch(
            "homeassistant.components.nanoleaf.config_flow.os.remove",
            return_value=None,
        ) as mock_remove,
        patch(
            "homeassistant.components.nanoleaf.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address(TEST_HOST),
                ip_addresses=[ip_address(TEST_HOST)],
                hostname="mock_hostname",
                name=f"{TEST_NAME}.{type_in_discovery}",
                port=None,
                properties={zeroconf.ATTR_PROPERTIES_ID: TEST_DEVICE_ID},
                type=type_in_discovery,
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
    }

    if remove_config:
        mock_save_json.assert_not_called()
        mock_remove.assert_called_once()
    else:
        mock_save_json.assert_called_once()
        mock_remove.assert_not_called()

    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_discovery(hass: HomeAssistant) -> None:
    """Test SSDP discovery."""
    with (
        patch(
            "homeassistant.components.nanoleaf.config_flow.load_json_object",
            return_value={},
        ),
        patch(
            "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
            return_value=_mock_nanoleaf(TEST_HOST, TEST_TOKEN),
        ),
        patch(
            "homeassistant.components.nanoleaf.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                upnp={},
                ssdp_headers={
                    "_host": TEST_HOST,
                    "nl-devicename": TEST_NAME,
                    "nl-deviceid": TEST_DEVICE_ID,
                },
            ),
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is None
        assert result["step_id"] == "link"

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_NAME
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
    }

    assert len(mock_setup_entry.mock_calls) == 1
