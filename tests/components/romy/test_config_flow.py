"""Test the ROMY config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.romy.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

MOCK_IP = "1.2.3.4"
VALID_CONFIG = {CONF_HOST: MOCK_IP, CONF_PORT: 8080, CONF_NAME: "myROMY"}
VALID_CONFIG_WITH_PASS = {
    CONF_HOST: MOCK_IP,
    CONF_PORT: 8080,
    CONF_NAME: "myROMY",
    CONF_PASSWORD: "password",
}


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["errors"] is not None
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


MOCK_IP = "1.2.3.4"
CONFIG = {CONF_HOST: MOCK_IP, CONF_PORT: 8080, CONF_NAME: "myROMY"}

INPUT_CONFIG = {
    CONF_HOST: CONFIG[CONF_HOST],
    CONF_PORT: CONFIG[CONF_PORT],
    CONF_NAME: CONFIG[CONF_NAME],
}


async def test_show_user_form_with_config(hass: HomeAssistant) -> None:
    """Test that the user set up form with config."""

    # patch for set robot name call
    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(True, "{}"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG,
        )

    assert "errors" not in result
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


INPUT_EMPTY_CONFIG = {}


async def test_show_user_form_with_empty_config(hass: HomeAssistant) -> None:
    """Test that the user set up form with empty config."""

    # patch for set robot name call
    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(True, "{}"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_EMPTY_CONFIG,
        )

    assert result["errors"] is not None
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    host="1.2.3.4",
    hostname="myROMY",
    port=8080,
    type="mock_type",
    addresses="addresses",
    name="myROMY",
    properties={zeroconf.ATTR_PROPERTIES_ID: "aicu-aicgsbksisfapcjqmqjq"},
)

INPUT_CONFIG_LOCKED = {
    CONF_HOST: CONFIG[CONF_HOST],
    CONF_PORT: CONFIG[CONF_PORT],
    CONF_NAME: CONFIG[CONF_NAME],
}


async def test_show_user_form_with_config_discovered_locked_robot(
    hass: HomeAssistant,
) -> None:
    """Test that we send unlock command if discover locked robot."""

    # patch for set robot name call
    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(True, "{}"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_LOCKED,
        )

    assert "errors" not in result
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_show_user_form_with_config_set_robot_name_call_fails(
    hass: HomeAssistant,
) -> None:
    """Test the case where the set robot name call fails."""

    # patch for set robot name call
    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(False, "{}"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=INPUT_CONFIG_LOCKED,
        )

    assert "errors" not in result
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    host="1.2.3.4",
    hostname="myROMY",
    port=8080,
    type="mock_type",
    addresses="addresses",
    name="myROMY",
    properties={zeroconf.ATTR_PROPERTIES_ID: "aicu-aicgsbksisfapcjqmqjq"},
)


async def test_zero_conf_unlocked_interface_robot(hass: HomeAssistant) -> None:
    """Test zerconf with already unlocked robot."""

    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(True, '{"name": "myROMY"}'),
    ), patch(
        "homeassistant.components.romy.config_flow.async_query_with_http_status",
        return_value=(True, "", 200),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_zero_conf_locked_interface_robot(hass: HomeAssistant) -> None:
    """Test zerconf with locked local http interface robot."""

    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(True, '{"name": "myROMY"}'),
    ), patch(
        "homeassistant.components.romy.config_flow.async_query_with_http_status",
        return_value=(False, "", 403),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_zero_conf_bad_request(hass: HomeAssistant) -> None:
    """Test zerconf with bad request response from robot."""

    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(True, '{"name": "myROMY"}'),
    ), patch(
        "homeassistant.components.romy.config_flow.async_query_with_http_status",
        return_value=(False, "", 400),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_zero_conf_robot_not_reachable(hass: HomeAssistant) -> None:
    """Test zerconf where robot is not reachable."""

    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(False, ""),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zero_conf_with_user_provided_password(hass: HomeAssistant) -> None:
    """Test zerconf with locked local http interface robot."""

    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(True, '{"name": "myROMY"}'),
    ):
        with patch(
            "homeassistant.components.romy.config_flow.async_query_with_http_status",
            return_value=(False, "", 403),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                data=DISCOVERY_INFO,
                context={"source": config_entries.SOURCE_ZEROCONF},
            )

        with patch(
            "homeassistant.components.romy.async_setup_entry",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_configure(
                flow_id=result["flow_id"], user_input=VALID_CONFIG_WITH_PASS
            )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_zero_conf_with_user_provided_wrong_password(hass: HomeAssistant) -> None:
    """Test zerconf with locked local http interface robot."""

    with patch(
        "homeassistant.components.romy.config_flow.async_query",
        return_value=(True, '{"name": "myROMY"}'),
    ):
        with patch(
            "homeassistant.components.romy.config_flow.async_query_with_http_status",
            return_value=(False, "", 403),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                data=DISCOVERY_INFO,
                context={"source": config_entries.SOURCE_ZEROCONF},
            )

        with patch(
            "homeassistant.components.romy.config_flow.async_query",
            return_value=(False, ""),
        ), patch(
            "homeassistant.components.romy.async_setup_entry",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_configure(
                flow_id=result["flow_id"], user_input=VALID_CONFIG_WITH_PASS
            )

    assert result.get("errors") == {CONF_PASSWORD: "wrong password"}
