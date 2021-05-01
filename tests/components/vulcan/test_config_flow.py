"""Test the Uonet+ Vulcan config flow."""
import os
import shutil
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vulcan import config_flow, const, register
from homeassistant.components.vulcan.config_flow import (
    ClientConnectionError,
    VulcanAPIException,
)
from homeassistant.const import CONF_PIN, CONF_REGION, CONF_SCAN_INTERVAL, CONF_TOKEN

from tests.common import MockConfigEntry


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.VulcanFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"


async def test_config_flow_auth_success(hass):
    """Test a successful config flow initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert result["data"] == {"student_id": "111", "login": "jan@fakelog.cf"}
    shutil.rmtree(".vulcan")


async def test_config_flow_reauth_success(hass):
    """Test a successful config flow reauth."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    shutil.rmtree(".vulcan")


async def test_config_flow_reauth_with_errors(hass):
    """Test reauth config flow with errors."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Invalid token."),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "invalid_token"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Expired token."),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "expired_token"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Invalid PIN."),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "invalid_pin"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Unknown error"),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=RuntimeError("Internal Server Error (ArgumentException)"),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "invalid_symbol"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=RuntimeError("Unknown error"),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=ClientConnectionError,
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=Exception,
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "unknown"}


async def test_multiple_config_entries(hass):
    """Test a successful config flow for multiple config entries."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)
    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": False},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert result["data"] == {"student_id": "111", "login": "jan@fakelog.cf"}
    shutil.rmtree(".vulcan")


async def test_multiple_config_entries_using_saved_credentials(hass):
    """Test a successful config flow for multiple config entries using saved credentials."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert result["data"] == {"student_id": "111", "login": "jan@fakelog.cf"}
    shutil.rmtree(".vulcan")


async def test_multiple_config_entries_without_valid_saved_credentials(hass):
    """Test a unsuccessful config flow for multiple config entries without valid saved credentials."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    os.mkdir(".vulcan")
    open(".vulcan/account-test2.json", "w")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    shutil.rmtree(".vulcan")


async def test_multiple_config_entries_without_valid_saved_credentials_2(hass):
    """Test a unsuccessful config flow for multiple config entries without valid saved credentials (different situation)."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    os.mkdir(".vulcan")
    open(".vulcan/keystore-test.json", "w")
    open(".vulcan/account-test2.json", "w")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    shutil.rmtree(".vulcan")


async def test_student_already_exists(hass):
    """Test config entry when student's entry already exists."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="111",
        data={"student_id": "111", "login": "jan@fakelog.cf"},
    ).add_to_hass(hass)

    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "all_student_already_configured"
    shutil.rmtree(".vulcan")


async def test_multiple_config_entries_with_selecting_saved_credentials(hass):
    """Test a successful config flow for multiple config entries with selecting saved credentials."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")

    open(".vulcan/keystore-test.json", "w")
    open(".vulcan/account-test.json", "w")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_saved_credentials"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"credentials": ".vulcan/account-jan@fakelog.cf.json"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert result["data"] == {"student_id": "111", "login": "jan@fakelog.cf"}
    shutil.rmtree(".vulcan")


async def test_multiple_config_entries_with_expired_credentials(hass):
    """Test adding next config entry when credentials is expired."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")

    open(".vulcan/keystore-test.json", "w")
    open(".vulcan/account-test.json", "w")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_saved_credentials"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        side_effect=VulcanAPIException("The certificate is not authorized."),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": ".vulcan/account-jan@fakelog.cf.json"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "expired_credentials"}

    shutil.rmtree(".vulcan")


async def test_multiple_config_entries_with_api_error(hass):
    """Test adding next config entry when unexpected api exception occurred."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")

    open(".vulcan/keystore-test.json", "w")
    open(".vulcan/account-test.json", "w")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_saved_credentials"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        side_effect=VulcanAPIException("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": ".vulcan/account-jan@fakelog.cf.json"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}

    shutil.rmtree(".vulcan")


async def test_multiple_config_entries_with_connection_issues(hass):
    """Test adding next config entry with connection issues."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")

    open(".vulcan/keystore-test.json", "w")
    open(".vulcan/account-test.json", "w")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_saved_credentials"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        side_effect=ClientConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": ".vulcan/account-jan@fakelog.cf.json"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "cannot_connect"}

    shutil.rmtree(".vulcan")


async def test_multiple_config_entries_with_unexpected_exception(hass):
    """Test adding next config entry with unexpected exception."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")

    open(".vulcan/keystore-test.json", "w")
    open(".vulcan/account-test.json", "w")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_saved_credentials"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": ".vulcan/account-jan@fakelog.cf.json"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}

    shutil.rmtree(".vulcan")


async def test_config_flow_auth_invalid_token(hass):
    """Test a config flow initialized by the user using invalid token."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "3S20000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "invalid_token"}


async def test_config_flow_auth_invalid_region(hass):
    """Test a config flow initialized by the user using invalid region."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "3S10000", CONF_REGION: "invalid_region", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "invalid_symbol"}


async def test_config_flow_auth_invalid_pin(hass):
    """Test a config flow initialized by the with invalid pin."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Invalid PIN."),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_pin"}


async def test_config_flow_auth_expired_token(hass):
    """Test a config flow initialized by the with expired token."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Expired token."),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "expired_token"}


async def test_config_flow_auth_api_unknown_error(hass):
    """Test a config flow with unknown API error."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


async def test_config_flow_auth_api_unknown_runtime_error(hass):
    """Test a config flow with runtime error."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=RuntimeError("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


async def test_config_flow_auth_connection_error(hass):
    """Test a config flow with connection error."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=ClientConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_auth_unknown_error(hass):
    """Test a config flow with unknown error."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "invalid_region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


async def test_options_flow(hass):
    """Test config flow options."""
    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="111",
        data={"student_id": "111", "login": "jan@fakelog.cf"},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SCAN_INTERVAL: 2137}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {CONF_SCAN_INTERVAL: 2137}

    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    shutil.rmtree(".vulcan")
