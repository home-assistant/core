"""Test the Nanoleaf config flow."""
from unittest.mock import patch

from pynanoleaf import InvalidToken, NotAuthorizingNewTokens, Unavailable

from homeassistant import config_entries
from homeassistant.components.nanoleaf.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

TEST_NAME = "Canvas ADF9"
TEST_HOST = "192.168.0.100"
TEST_TOKEN = "R34F1c92FNv3pcZs4di17RxGqiLSwHM"
TEST_OTHER_TOKEN = "Qs4dxGcHR34l29RF1c92FgiLQBt3pcM"
TEST_DEVICE_ID = "5E:2E:EA:XX:XX:XX"
TEST_OTHER_DEVICE_ID = "5E:2E:EA:YY:YY:YY"


async def test_user_unavailable(hass: HomeAssistant) -> None:
    """Test we handle Unavailable errors."""
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
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result3["step_id"] == "link"

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=Unavailable("message"),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result4["type"] == "form"
    assert result4["step_id"] == "user"
    assert result4["errors"] == {"base": "cannot_connect"}
    assert not result4["last_step"]

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        return_value=None,
    ):
        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
            },
        )
    assert result5["step_id"] == "link"

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        return_value=None,
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        side_effect=Unavailable("message"),
    ):
        result6 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result6["type"] == "form"
    assert result6["step_id"] == "user"
    assert result6["errors"] == {"base": "cannot_connect"}
    assert not result6["last_step"]


async def test_user_not_authorizing_new_tokens(hass: HomeAssistant) -> None:
    """Test we handle NotAuthorizingNewTokens errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    assert not result["last_step"]
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=NotAuthorizingNewTokens("message"),
    ):
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

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf.authorize",
        side_effect=NotAuthorizingNewTokens("message"),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result4["type"] == "form"
    assert result4["step_id"] == "link"
    assert result4["errors"] == {"base": "not_allowing_new_tokens"}


async def test_user_exception(hass: HomeAssistant) -> None:
    """Test we handle Exception errors."""
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
    assert result5["type"] == "form"
    assert result5["step_id"] == "user"
    assert result5["errors"] == {"base": "unknown"}
    assert not result5["last_step"]


async def test_zeroconf_discovery(hass: HomeAssistant) -> None:
    """Test zeroconfig discovery flow init."""
    zeroconf = "_nanoleafms._tcp.local"
    with patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        return_value={"name": TEST_NAME},
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.load_json",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data={
                "host": TEST_HOST,
                "name": f"{TEST_NAME}.{zeroconf}",
                "type": zeroconf,
                "properties": {"id": TEST_DEVICE_ID},
            },
        )
    assert result["type"] == "form"
    assert result["step_id"] == "link"


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


async def test_import_config_invalid_token(hass: HomeAssistant) -> None:
    """Test configuration import with invalid token."""
    with patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        side_effect=InvalidToken("message"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "invalid_token"}


async def test_import_last_discovery_integration_host_zeroconf(
    hass: HomeAssistant,
) -> None:
    """
    Test discovery integration import from < 2021.4 (host) with zeroconf.

    Device is last in Nanoleaf config file.
    """
    zeroconf = "_nanoleafapi._tcp.local"
    with patch(
        "homeassistant.components.nanoleaf.config_flow.load_json",
        return_value={TEST_HOST: {"token": TEST_TOKEN}},
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        return_value={"name": TEST_NAME},
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.save_json",
        return_value=None,
    ), patch(
        "homeassistant.components.nanoleaf.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data={
                "host": TEST_HOST,
                "name": f"{TEST_NAME}.{zeroconf}",
                "type": zeroconf,
                "properties": {"id": TEST_DEVICE_ID},
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_not_last_discovery_integration_device_id_homekit(
    hass: HomeAssistant,
) -> None:
    """
    Test discovery integration import from >= 2021.4 (device_id) with homekit.

    Device is not the only one in the Nanoleaf config file.
    """
    homekit = "_hap._tcp.local"
    with patch(
        "homeassistant.components.nanoleaf.config_flow.load_json",
        return_value={
            TEST_DEVICE_ID: {"token": TEST_TOKEN},
            TEST_OTHER_DEVICE_ID: {"token": TEST_OTHER_TOKEN},
        },
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.pynanoleaf_get_info",
        return_value={"name": TEST_NAME},
    ), patch(
        "homeassistant.components.nanoleaf.config_flow.save_json",
        return_value=None,
    ), patch(
        "homeassistant.components.nanoleaf.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={
                "host": TEST_HOST,
                "name": f"{TEST_NAME}.{homekit}",
                "type": homekit,
                "properties": {"id": TEST_DEVICE_ID},
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
