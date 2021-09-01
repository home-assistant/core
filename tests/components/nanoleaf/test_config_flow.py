"""Test the Nanoleaf config flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from pynanoleaf import InvalidToken, NotAuthorizingNewTokens, Unavailable
from pynanoleaf.pynanoleaf import NanoleafError
import pytest

from homeassistant import config_entries
from homeassistant.components.nanoleaf.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_NAME = "Canvas ADF9"
TEST_HOST = "192.168.0.100"
TEST_OTHER_HOST = "192.168.0.200"
TEST_TOKEN = "R34F1c92FNv3pcZs4di17RxGqiLSwHM"
TEST_OTHER_TOKEN = "Qs4dxGcHR34l29RF1c92FgiLQBt3pcM"
TEST_DEVICE_ID = "5E:2E:EA:XX:XX:XX"
TEST_OTHER_DEVICE_ID = "5E:2E:EA:YY:YY:YY"


async def test_user_unavailable_user_step_link_step(hass: HomeAssistant) -> None:
    """Test we handle Unavailable in user and link step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=Unavailable("message"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result2["type"] == "form"
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
    assert result2["type"] == "form"
    assert result2["step_id"] == "link"

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=Unavailable("message"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result3["type"] == "abort"
    assert result3["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    "error, reason",
    [
        (Unavailable("message"), "cannot_connect"),
        (InvalidToken("message"), "invalid_token"),
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
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result2["type"] == "form"
    assert result2["step_id"] == "link"

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        return_value=None,
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        side_effect=error,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result3["type"] == "abort"
    assert result3["reason"] == reason


async def test_user_not_authorizing_new_tokens_user_step_link_step(
    hass: HomeAssistant,
) -> None:
    """Test we handle NotAuthorizingNewTokens in user step and link step."""
    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
    ) as mock_nanoleaf, patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        return_value={"name": TEST_NAME},
    ), patch(
        "homeassistant.components.nanoleaf.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        nanoleaf = mock_nanoleaf.return_value
        nanoleaf.authorize.side_effect = NotAuthorizingNewTokens(
            "Not authorizing new tokens"
        )
        nanoleaf.host = TEST_HOST
        nanoleaf.token = TEST_TOKEN

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["errors"] is None
        assert result["step_id"] == "user"
        assert not result["last_step"]

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
        assert result2["type"] == "form"
        assert result2["errors"] is None
        assert result2["step_id"] == "link"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        assert result3["type"] == "form"
        assert result3["errors"] is None
        assert result3["step_id"] == "link"

        result4 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result4["type"] == "form"
        assert result4["errors"] == {"base": "not_allowing_new_tokens"}
        assert result4["step_id"] == "link"

        nanoleaf.authorize.side_effect = None
        nanoleaf.authorize.return_value = None

        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        assert result5["type"] == "create_entry"
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
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}
    assert not result2["last_step"]

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        return_value=None,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result3["step_id"] == "link"

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=Exception,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result4["type"] == "form"
    assert result4["step_id"] == "link"
    assert result4["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        return_value=None,
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        side_effect=Exception,
    ):
        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result5["type"] == "abort"
    assert result5["reason"] == "unknown"


@pytest.mark.parametrize(
    "source, type_in_discovery_info",
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
    with patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        return_value={"name": TEST_NAME},
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.load_json",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data={
                "host": TEST_HOST,
                "name": f"{TEST_NAME}.{type_in_discovery_info}",
                "type": type_in_discovery_info,
                "properties": {"id": TEST_DEVICE_ID},
            },
        )
    assert result["type"] == "form"
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
        side_effect=Unavailable("message"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_reauth(hass: HomeAssistant) -> None:
    """Test Nanoleaf reauth flow."""
    nanoleaf = MagicMock()
    nanoleaf.host = TEST_HOST
    nanoleaf.token = TEST_TOKEN

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_NAME,
        data={CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_OTHER_TOKEN},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
        return_value=nanoleaf,
    ), patch(
        "homeassistant.components.nanoleaf.async_setup_entry",
        return_value=True,
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
        assert result["type"] == "form"
        assert result["step_id"] == "link"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"

    assert entry.data[CONF_HOST] == TEST_HOST
    assert entry.data[CONF_TOKEN] == TEST_TOKEN


async def test_import_config(hass: HomeAssistant) -> None:
    """Test configuration import."""
    with patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        return_value={"name": TEST_NAME},
    ), patch(
        "homeassistant.components.nanoleaf.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )
    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "error, reason",
    [
        (Unavailable("message"), "cannot_connect"),
        (InvalidToken("message"), "invalid_token"),
        (Exception, "unknown"),
    ],
)
async def test_import_config_error(
    hass: HomeAssistant, error: NanoleafError, reason: str
) -> None:
    """Test configuration import with errors in setup_finish."""
    with patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )
    assert result["type"] == "abort"
    assert result["reason"] == reason


@pytest.mark.parametrize(
    "source, type_in_discovery",
    [
        (config_entries.SOURCE_HOMEKIT, "_hap._tcp.local"),
        (config_entries.SOURCE_ZEROCONF, "_nanoleafms._tcp.local"),
        (config_entries.SOURCE_ZEROCONF, "_nanoleafapi._tcp.local"),
    ],
)
@pytest.mark.parametrize(
    "nanoleaf_conf_file, remove_config",
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
    """
    Test discovery integration import.

    Test with different discovery flow sources and corresponding types.
    Test with different .nanoleaf_conf files with device_id (>= 2021.4), host (< 2021.4) and combination.
    Test removing the .nanoleaf_conf file if it was the only device in the file.
    Test updating the .nanoleaf_conf file if it was not the only device in the file.
    """
    with patch(
        "homeassistant.components.nanoleaf.config_flow.load_json",
        return_value=dict(nanoleaf_conf_file),
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        return_value={"name": TEST_NAME},
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.save_json",
        return_value=None,
    ) as mock_save_json, patch(
        "homeassistant.components.nanoleaf.config_flow.os.remove",
        return_value=None,
    ) as mock_remove, patch(
        "homeassistant.components.nanoleaf.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data={
                "host": TEST_HOST,
                "name": f"{TEST_NAME}.{type_in_discovery}",
                "type": type_in_discovery,
                "properties": {"id": TEST_DEVICE_ID},
            },
        )
    assert result["type"] == "create_entry"
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

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
