"""Test the ROMY config flow."""

from ipaddress import ip_address
from unittest.mock import Mock, PropertyMock, patch

from romy import RomyRobot

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.romy.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def _create_mocked_romy(
    is_initialized,
    is_unlocked,
    name="Agon",
    user_name="MyROMY",
    unique_id="aicu-aicgsbksisfapcjqmqjq",
    model="005:000:000:000:005",
    port=8080,
):
    mocked_romy = Mock(spec_set=RomyRobot)
    type(mocked_romy).is_initialized = PropertyMock(return_value=is_initialized)
    type(mocked_romy).is_unlocked = PropertyMock(return_value=is_unlocked)
    type(mocked_romy).name = PropertyMock(return_value=name)
    type(mocked_romy).user_name = PropertyMock(return_value=user_name)
    type(mocked_romy).unique_id = PropertyMock(return_value=unique_id)
    type(mocked_romy).port = PropertyMock(return_value=port)
    type(mocked_romy).model = PropertyMock(return_value=model)

    return mocked_romy


CONFIG = {CONF_HOST: "1.2.3.4", CONF_PASSWORD: "12345678"}

INPUT_CONFIG_HOST = {
    CONF_HOST: CONFIG[CONF_HOST],
}


async def test_show_user_form_robot_is_offline_and_locked(hass: HomeAssistant) -> None:
    """Test that the user set up form with config."""

    # Robot not reachable
    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(False, False),
    ):
        result1 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_HOST,
        )

        assert result1["errors"].get("host") == "cannot_connect"
        assert result1["step_id"] == "user"
        assert result1["type"] is FlowResultType.FORM

    # Robot is locked
    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(True, False),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"host": "1.2.3.4"}
        )

        assert result2["step_id"] == "password"
        assert result2["type"] is FlowResultType.FORM

    # Robot is initialized and unlocked
    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(True, True),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"password": "12345678"}
        )

        assert "errors" not in result3
        assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_show_user_form_robot_unlock_with_password(hass: HomeAssistant) -> None:
    """Test that the user set up form with config."""

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(True, False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_HOST,
        )

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(True, False),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "12345678"}
        )

        assert result2["errors"] == {"password": "invalid_auth"}
        assert result2["step_id"] == "password"
        assert result2["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(False, False),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"password": "12345678"}
        )

        assert result3["errors"] == {"password": "cannot_connect"}
        assert result3["step_id"] == "password"
        assert result3["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(True, True),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"password": "12345678"}
        )

        assert "errors" not in result4
        assert result4["type"] is FlowResultType.CREATE_ENTRY


async def test_show_user_form_robot_reachable_again(hass: HomeAssistant) -> None:
    """Test that the user set up form with config."""

    # Robot not reachable
    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(False, False),
    ):
        result1 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_HOST,
        )

        assert result1["errors"].get("host") == "cannot_connect"
        assert result1["step_id"] == "user"
        assert result1["type"] is FlowResultType.FORM

    # Robot is locked
    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(True, True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"host": "1.2.3.4"}
        )

        assert "errors" not in result2
        assert result2["type"] is FlowResultType.CREATE_ENTRY


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

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(True, False),
    ):
        result1 = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result1["step_id"] == "password"
    assert result1["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(True, True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"password": "12345678"}
        )

        assert "errors" not in result2
        assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_zero_conf_uninitialized_robot(hass: HomeAssistant) -> None:
    """Test zerconf which discovered locked robot."""

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(False, False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["reason"] == "cannot_connect"
    assert result["type"] is FlowResultType.ABORT


async def test_zero_conf_unlocked_interface_robot(hass: HomeAssistant) -> None:
    """Test zerconf which discovered already unlocked robot."""

    with patch(
        "homeassistant.components.romy.config_flow.romy.create_romy",
        return_value=_create_mocked_romy(True, True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4"},
    )

    assert result["data"]
    assert result["data"][CONF_HOST] == "1.2.3.4"

    assert result["result"]
    assert result["result"].unique_id == "aicu-aicgsbksisfapcjqmqjq"

    assert result["type"] is FlowResultType.CREATE_ENTRY
