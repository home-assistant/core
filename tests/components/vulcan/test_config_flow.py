"""Test the Uonet+ Vulcan config flow."""
import shutil

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vulcan import config_flow, const, register
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

    assert result["type"] == "create_entry"
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


async def test_multiple_config_entries(hass):
    """Test a successful config flow for multiple config entries."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

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

    assert result["type"] == "create_entry"
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

    assert result["type"] == "create_entry"
    assert result["title"] == "Jan Kowalski"
    assert result["data"] == {"student_id": "111", "login": "jan@fakelog.cf"}
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

    assert result["type"] == "create_entry"
    assert result["title"] == "Jan Kowalski"
    assert result["data"] == {"student_id": "111", "login": "jan@fakelog.cf"}
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
