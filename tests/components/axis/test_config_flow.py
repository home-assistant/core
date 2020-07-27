"""Test Axis config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.axis import config_flow
from homeassistant.components.axis.const import (
    CONF_EVENTS,
    CONF_MODEL,
    CONF_STREAM_PROFILE,
    DEFAULT_STREAM_PROFILE,
    DOMAIN as AXIS_DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from .test_device import MAC, MODEL, NAME, setup_axis_integration, vapix_session_request

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_flow_manual_configuration(hass):
    """Test that config flow works."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("axis.vapix.session_request", new=vapix_session_request):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PORT: 80,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == f"M1065-LW - {MAC}"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_PORT: 80,
        CONF_MAC: MAC,
        CONF_MODEL: "M1065-LW",
        CONF_NAME: "M1065-LW 0",
    }


async def test_manual_configuration_update_configuration(hass):
    """Test that config flow fails on already configured device."""
    device = await setup_axis_integration(hass)

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("axis.vapix.session_request", new=vapix_session_request):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "2.3.4.5",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PORT: 80,
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert device.host == "2.3.4.5"


async def test_flow_fails_already_configured(hass):
    """Test that config flow fails on already configured device."""
    await setup_axis_integration(hass)

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("axis.vapix.session_request", new=vapix_session_request):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PORT: 80,
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_flow_fails_faulty_credentials(hass):
    """Test that config flow fails on faulty credentials."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.axis.config_flow.get_device",
        side_effect=config_flow.AuthenticationRequired,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PORT: 80,
            },
        )

    assert result["errors"] == {"base": "faulty_credentials"}


async def test_flow_fails_device_unavailable(hass):
    """Test that config flow fails on device unavailable."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.axis.config_flow.get_device",
        side_effect=config_flow.CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PORT: 80,
            },
        )

    assert result["errors"] == {"base": "device_unavailable"}


async def test_flow_create_entry_multiple_existing_entries_of_same_model(hass):
    """Test that create entry can generate a name with other entries."""
    entry = MockConfigEntry(
        domain=AXIS_DOMAIN, data={CONF_NAME: "M1065-LW 0", CONF_MODEL: "M1065-LW"},
    )
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=AXIS_DOMAIN, data={CONF_NAME: "M1065-LW 1", CONF_MODEL: "M1065-LW"},
    )
    entry2.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("axis.vapix.session_request", new=vapix_session_request):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PORT: 80,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == f"M1065-LW - {MAC}"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_PORT: 80,
        CONF_MAC: MAC,
        CONF_MODEL: "M1065-LW",
        CONF_NAME: "M1065-LW 2",
    }

    assert result["data"][CONF_NAME] == "M1065-LW 2"


async def test_zeroconf_flow(hass):
    """Test that zeroconf discovery for new devices work."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            "hostname": "name",
            "properties": {"macaddress": MAC},
        },
        context={"source": "zeroconf"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("axis.vapix.session_request", new=vapix_session_request):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PORT: 80,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == f"M1065-LW - {MAC}"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_PORT: 80,
        CONF_MAC: MAC,
        CONF_MODEL: "M1065-LW",
        CONF_NAME: "M1065-LW 0",
    }

    assert result["data"][CONF_NAME] == "M1065-LW 0"


async def test_zeroconf_flow_already_configured(hass):
    """Test that zeroconf doesn't setup already configured devices."""
    device = await setup_axis_integration(hass)
    assert device.host == "1.2.3.4"

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            "hostname": "name",
            "properties": {"macaddress": MAC},
        },
        context={"source": "zeroconf"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert device.host == "1.2.3.4"


async def test_zeroconf_flow_updated_configuration(hass):
    """Test that zeroconf update configuration with new parameters."""
    device = await setup_axis_integration(hass)
    assert device.host == "1.2.3.4"
    assert device.config_entry.data == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
        CONF_USERNAME: "root",
        CONF_PASSWORD: "pass",
        CONF_MAC: MAC,
        CONF_MODEL: MODEL,
        CONF_NAME: NAME,
    }

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN,
        data={
            CONF_HOST: "2.3.4.5",
            CONF_PORT: 8080,
            "hostname": "name",
            "properties": {"macaddress": MAC},
        },
        context={"source": "zeroconf"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert device.config_entry.data == {
        CONF_HOST: "2.3.4.5",
        CONF_PORT: 8080,
        CONF_USERNAME: "root",
        CONF_PASSWORD: "pass",
        CONF_MAC: MAC,
        CONF_MODEL: MODEL,
        CONF_NAME: NAME,
    }


async def test_zeroconf_flow_ignore_non_axis_device(hass):
    """Test that zeroconf doesn't setup devices with link local addresses."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN,
        data={CONF_HOST: "169.254.3.4", "properties": {"macaddress": "01234567890"}},
        context={"source": "zeroconf"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_axis_device"


async def test_zeroconf_flow_ignore_link_local_address(hass):
    """Test that zeroconf doesn't setup devices with link local addresses."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN,
        data={CONF_HOST: "169.254.3.4", "properties": {"macaddress": MAC}},
        context={"source": "zeroconf"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "link_local_address"


async def test_option_flow(hass):
    """Test config flow options."""
    device = await setup_axis_integration(hass)
    assert device.option_stream_profile == DEFAULT_STREAM_PROFILE

    result = await hass.config_entries.options.async_init(device.config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "configure_stream"
    assert set(result["data_schema"].schema[CONF_STREAM_PROFILE].container) == {
        DEFAULT_STREAM_PROFILE,
        "profile_1",
        "profile_2",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_STREAM_PROFILE: "profile_1"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_EVENTS: True,
        CONF_STREAM_PROFILE: "profile_1",
    }
    assert device.option_stream_profile == "profile_1"
