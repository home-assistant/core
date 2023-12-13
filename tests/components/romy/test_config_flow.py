"""Test the ROMY config flow."""
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.romy.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_UUID
from homeassistant.core import HomeAssistant


def _create_mocked_romy(
    is_initialized,
    is_unlocked,
    name="Nadine",
    unique_id="aicu-aicgsbksisfapcjqmqjq",
    port=8080,
    model="005:000:000:000:005",
    firmware="CHRON-0.0.1-new-wifi-release-3.15.3175",
):
    mocked_romy = AsyncMock(MagicMock)
    type(mocked_romy).is_initialized = PropertyMock(return_value=is_initialized)
    type(mocked_romy).is_unlocked = PropertyMock(return_value=is_unlocked)
    type(mocked_romy).name = PropertyMock(return_value=name)
    type(mocked_romy).unique_id = PropertyMock(return_value=unique_id)
    type(mocked_romy).port = PropertyMock(return_value=port)
    type(mocked_romy).model = PropertyMock(return_value=model)
    type(mocked_romy).firmware = PropertyMock(return_value=firmware)

    # Mock async methods
    async def mock_set_name(new_name):
        mocked_romy.name = PropertyMock(return_value=new_name)
        return True, '{"success": true}'

    type(mocked_romy).set_name = AsyncMock(side_effect=mock_set_name)

    async def mock_async_update():
        return

    type(mocked_romy).async_update = AsyncMock(side_effect=mock_async_update)

    return mocked_romy


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["errors"] is not None
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


CONFIG = {CONF_HOST: "1.2.3.4", CONF_NAME: "myROMY", CONF_PASSWORD: "12345678"}


INPUT_CONFIG = {
    CONF_HOST: CONFIG[CONF_HOST],
    CONF_NAME: CONFIG[CONF_NAME],
}


async def test_show_user_form_with_config(hass: HomeAssistant) -> None:
    """Test that the user set up form with config."""

    mocked_romy = _create_mocked_romy(
        is_initialized=True,
        is_unlocked=True,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_romy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG,
        )

    assert "errors" not in result
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


INPUT_CONFIG_WITHOUT_NAME = {
    CONF_HOST: CONFIG[CONF_HOST],
    CONF_NAME: None,
}


async def test_show_user_form_with_config_without_name(hass: HomeAssistant) -> None:
    """Test that the user set up form with config."""

    mocked_romy = _create_mocked_romy(
        is_initialized=True,
        is_unlocked=True,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_romy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_WITHOUT_NAME,
        )

    assert "errors" not in result
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


INPUT_CONFIG_WITH_PASS = {
    CONF_HOST: CONFIG[CONF_HOST],
    CONF_NAME: CONFIG[CONF_NAME],
    CONF_PASSWORD: CONFIG[CONF_PASSWORD],
}


async def test_show_user_form_with_config_which_contains_password(
    hass: HomeAssistant,
) -> None:
    """Test that the user set up form with config which contains password."""

    mocked_romy = _create_mocked_romy(
        is_initialized=True,
        is_unlocked=True,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_romy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_WITH_PASS,
        )

    assert "errors" not in result
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["context"]["unique_id"] == "aicu-aicgsbksisfapcjqmqjq"


async def test_show_user_form_with_config_which_contains_wrong_host(
    hass: HomeAssistant,
) -> None:
    """Test that the user set up form with config which contains password."""

    mocked_romy = _create_mocked_romy(
        is_initialized=False,
        is_unlocked=False,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_romy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_WITH_PASS,
        )

    assert result["errors"].get("host") == "cannot_connect"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_user_form_with_config_which_contains_wrong_password(
    hass: HomeAssistant,
) -> None:
    """Test that the user set up form with config which contains password."""

    mocked_romy = _create_mocked_romy(
        is_initialized=True,
        is_unlocked=False,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_romy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_WITH_PASS,
        )

    assert result["errors"].get("password") == "invalid_auth"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


# zero conf tests
###################

DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.2.3.4"),
    ip_addresses=[ip_address("1.2.3.4")],
    port=8080,
    hostname="aicu-aicgsbksisfapcjqmqjq.local",
    type="mock_type",
    name="myROMY",
    properties={zeroconf.ATTR_PROPERTIES_ID: "aicu-aicgsbksisfapcjqmqjqZERO"},
)


async def test_zero_conf_locked_interface_robot(hass: HomeAssistant) -> None:
    """Test zerconf which discovered locked robot."""

    mocked_romy = _create_mocked_romy(
        is_initialized=True,
        is_unlocked=False,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_romy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_zero_conf_unlocked_interface_robot(hass: HomeAssistant) -> None:
    """Test zerconf which discovered already unlocked robot."""

    mocked_romy = _create_mocked_romy(
        is_initialized=True,
        is_unlocked=True,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_romy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    assert result["data"]
    assert result["data"][CONF_HOST] == "1.2.3.4"
    assert result["data"][CONF_UUID] == "aicu-aicgsbksisfapcjqmqjq"

    assert result["result"]
    assert result["result"].unique_id == "aicu-aicgsbksisfapcjqmqjq"
