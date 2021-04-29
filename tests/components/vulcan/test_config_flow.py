"""Test the Uonet+ Vulcan config flow."""
import shutil

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vulcan import config_flow, const, register
from homeassistant.const import CONF_PIN, CONF_REGION, CONF_TOKEN

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

    assert result["type"] == "form"
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


async def test_multiple_config_entries(hass):
    """Test a successful config flow initialized by the user."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": False},
    )

    assert result["type"] == "form"
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
    """Test a successful config flow initialized by the user."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={"student_id": "123456", "login": "example@mail.com"},
    ).add_to_hass(hass)

    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
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


async def test_config_flow_auth_invalid_token(hass):
    """Test a successful config flow initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "3S20000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "invalid_token"}


async def test_config_flow_auth_invalid_region(hass):
    """Test a successful config flow initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "3S10000", CONF_REGION: "invalid_region", CONF_PIN: "000000"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "invalid_symbol"}
