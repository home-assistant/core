"""Test the ROMY config flow."""
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.romy.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant


def _create_mocked_romy(
    is_initialized,
    is_unlocked,
    user_name="MyROMY",
    unique_id="aicu-aicgsbksisfapcjqmqjq",
    model="005:000:000:000:005",
    port=8080,
):
    mocked_romy = AsyncMock(MagicMock)
    type(mocked_romy).is_initialized = PropertyMock(return_value=is_initialized)
    type(mocked_romy).is_unlocked = PropertyMock(return_value=is_unlocked)
    type(mocked_romy).user_name = PropertyMock(return_value=user_name)
    type(mocked_romy).unique_id = PropertyMock(return_value=unique_id)
    type(mocked_romy).port = PropertyMock(return_value=port)
    type(mocked_romy).model = PropertyMock(return_value=model)

    # Mock async methods
    async def mock_set_name(new_name):
        mocked_romy.name = PropertyMock(return_value=new_name)
        return True, '{"success": true}'

    type(mocked_romy).set_name = AsyncMock(side_effect=mock_set_name)

    async def mock_async_update():
        return

    type(mocked_romy).async_update = AsyncMock(side_effect=mock_async_update)

    return mocked_romy


CONFIG = {CONF_HOST: "1.2.3.4", CONF_PASSWORD: "12345678"}

INPUT_CONFIG_HOST = {
    CONF_HOST: CONFIG[CONF_HOST],
}

INPUT_CONFIG_PASS = {
    CONF_PASSWORD: CONFIG[CONF_PASSWORD],
}


# user conf tests
###################
async def test_show_user_form(hass: HomeAssistant) -> None:
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
            data=INPUT_CONFIG_HOST,
        )

    assert "errors" not in result
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_show_user_form_with_wrong_host(
    hass: HomeAssistant,
) -> None:
    """Test that the user enters wrong host."""

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
            data=INPUT_CONFIG_HOST,
        )

    assert result["errors"].get("host") == "cannot_connect"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_user_with_locked_interface_robot_with_wrong_password(
    hass: HomeAssistant,
) -> None:
    """Test with a locked interface robot."""

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
            data=INPUT_CONFIG_HOST,
        )

    assert result["step_id"] == "password"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_romy,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=INPUT_CONFIG_PASS
        )

        assert result["step_id"] == "password"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_user_with_locked_interface_robot_with_correct_password(
    hass: HomeAssistant,
) -> None:
    """Test with a locked interface robot."""

    mocked_locked_romy = _create_mocked_romy(
        is_initialized=True,
        is_unlocked=False,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_locked_romy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_HOST,
        )

    assert result["step_id"] == "password"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    mocked_unlocked_romy = _create_mocked_romy(
        is_initialized=True,
        is_unlocked=True,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_unlocked_romy,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=INPUT_CONFIG_PASS
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_show_user_with_locked_interface_robot_with_connection_loss(
    hass: HomeAssistant,
) -> None:
    """Test with a locked interface robot."""

    mocked_locked_romy = _create_mocked_romy(
        is_initialized=True,
        is_unlocked=False,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_locked_romy,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_HOST,
        )

    assert result["step_id"] == "password"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    mocked_disconnected_romy = _create_mocked_romy(
        is_initialized=False,
        is_unlocked=False,
    )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=mocked_disconnected_romy,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=INPUT_CONFIG_PASS
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"


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

    assert result["step_id"] == "password"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_zero_conf_uninitialized_robot(hass: HomeAssistant) -> None:
    """Test zerconf which discovered locked robot."""

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
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


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

    assert result["result"]
    assert result["result"].unique_id == "aicu-aicgsbksisfapcjqmqjq"
