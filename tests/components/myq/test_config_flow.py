"""Test the MyQ config flow."""
from unittest.mock import patch

from pymyq.errors import InvalidCredentialsError, MyQError

from homeassistant import config_entries, setup
from homeassistant.components.myq.const import CONF_USERAGENT, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


async def test_form_user(hass):
    """Test we get the user form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.myq.config_flow.pymyq.login",
        return_value=True,
    ), patch(
        "homeassistant.components.myq.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.myq.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "user_agent": "test-useragent",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "user_agent": "test-useragent",
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass):
    """Test config flow options."""
    conf = {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_USERAGENT: "test-useragent",
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abcde12345",
        data=conf,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.myq.config_flow.pymyq.login", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == "form"
        assert result["step_id"] == "init"
        assert config_entry.options == {CONF_USERAGENT: "test-useragent"}

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_USERAGENT: "test-useragent2"}
        )

        assert result["type"] == "create_entry"
        assert config_entry.options == {CONF_USERAGENT: "test-useragent2"}


async def test_import(hass):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.myq.config_flow.pymyq.login",
        return_value=True,
    ), patch(
        "homeassistant.components.myq.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.myq.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "username": "test-username",
                "password": "test-password",
                "user_agent": "test-useragent",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "test-username"
    assert result["data"] == {
        "username": "test-username",
        "password": "test-password",
        "user_agent": "test-useragent",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.myq.config_flow.pymyq.login",
        side_effect=InvalidCredentialsError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "user_agent": "test-useragent",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.myq.config_flow.pymyq.login",
        side_effect=MyQError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "user_agent": "test-useragent",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_homekit(hass):
    """Test that we abort from homekit if myq is already setup."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "homekit"},
        data={"properties": {"id": "AA:BB:CC:DD:EE:FF"}},
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    flow = next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert flow["context"]["unique_id"] == "AA:BB:CC:DD:EE:FF"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock", CONF_USERAGENT: "mock"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "homekit"},
        data={"properties": {"id": "AA:BB:CC:DD:EE:FF"}},
    )
    assert result["type"] == "abort"
