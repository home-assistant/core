"""Test Axis config flow."""
from unittest.mock import Mock, patch

from homeassistant.components import axis
from homeassistant.components.axis import config_flow

from .test_device import MAC, MODEL, NAME, setup_axis_integration

from tests.common import MockConfigEntry, mock_coro


def setup_mock_axis_device(mock_device):
    """Prepare mock axis device."""

    def mock_constructor(loop, host, username, password, port, web_proto):
        """Fake the controller constructor."""
        mock_device.loop = loop
        mock_device.host = host
        mock_device.username = username
        mock_device.password = password
        mock_device.port = port
        return mock_device

    mock_device.side_effect = mock_constructor
    mock_device.vapix.params.system_serialnumber = MAC
    mock_device.vapix.params.prodnbr = "prodnbr"
    mock_device.vapix.params.prodtype = "prodtype"
    mock_device.vapix.params.firmware_version = "firmware_version"


async def test_flow_manual_configuration(hass):
    """Test that config flow works."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("axis.AxisDevice") as mock_device:

        setup_mock_axis_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_HOST: "1.2.3.4",
                config_flow.CONF_USERNAME: "user",
                config_flow.CONF_PASSWORD: "pass",
                config_flow.CONF_PORT: 80,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == f"prodnbr - {MAC}"
    assert result["data"] == {
        config_flow.CONF_HOST: "1.2.3.4",
        config_flow.CONF_USERNAME: "user",
        config_flow.CONF_PASSWORD: "pass",
        config_flow.CONF_PORT: 80,
        config_flow.CONF_MAC: MAC,
        config_flow.CONF_MODEL: "prodnbr",
        config_flow.CONF_NAME: "prodnbr 0",
    }


async def test_manual_configuration_update_configuration(hass):
    """Test that config flow fails on already configured device."""
    device = await setup_axis_integration(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_device = Mock()
    mock_device.vapix.params.system_serialnumber = MAC

    with patch(
        "homeassistant.components.axis.config_flow.get_device",
        return_value=mock_coro(mock_device),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_HOST: "2.3.4.5",
                config_flow.CONF_USERNAME: "user",
                config_flow.CONF_PASSWORD: "pass",
                config_flow.CONF_PORT: 80,
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert device.config_entry.data[config_flow.CONF_HOST] == "2.3.4.5"


async def test_flow_fails_already_configured(hass):
    """Test that config flow fails on already configured device."""
    await setup_axis_integration(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_device = Mock()
    mock_device.vapix.params.system_serialnumber = MAC

    with patch(
        "homeassistant.components.axis.config_flow.get_device",
        return_value=mock_coro(mock_device),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_HOST: "1.2.3.4",
                config_flow.CONF_USERNAME: "user",
                config_flow.CONF_PASSWORD: "pass",
                config_flow.CONF_PORT: 80,
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_flow_fails_faulty_credentials(hass):
    """Test that config flow fails on faulty credentials."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
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
                config_flow.CONF_HOST: "1.2.3.4",
                config_flow.CONF_USERNAME: "user",
                config_flow.CONF_PASSWORD: "pass",
                config_flow.CONF_PORT: 80,
            },
        )

    assert result["errors"] == {"base": "faulty_credentials"}


async def test_flow_fails_device_unavailable(hass):
    """Test that config flow fails on device unavailable."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
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
                config_flow.CONF_HOST: "1.2.3.4",
                config_flow.CONF_USERNAME: "user",
                config_flow.CONF_PASSWORD: "pass",
                config_flow.CONF_PORT: 80,
            },
        )

    assert result["errors"] == {"base": "device_unavailable"}


async def test_flow_create_entry_multiple_existing_entries_of_same_model(hass):
    """Test that create entry can generate a name with other entries."""
    entry = MockConfigEntry(
        domain=axis.DOMAIN,
        data={config_flow.CONF_NAME: "prodnbr 0", config_flow.CONF_MODEL: "prodnbr"},
    )
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=axis.DOMAIN,
        data={config_flow.CONF_NAME: "prodnbr 1", config_flow.CONF_MODEL: "prodnbr"},
    )
    entry2.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("axis.AxisDevice") as mock_device:

        setup_mock_axis_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_HOST: "1.2.3.4",
                config_flow.CONF_USERNAME: "user",
                config_flow.CONF_PASSWORD: "pass",
                config_flow.CONF_PORT: 80,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == f"prodnbr - {MAC}"
    assert result["data"] == {
        config_flow.CONF_HOST: "1.2.3.4",
        config_flow.CONF_USERNAME: "user",
        config_flow.CONF_PASSWORD: "pass",
        config_flow.CONF_PORT: 80,
        config_flow.CONF_MAC: MAC,
        config_flow.CONF_MODEL: "prodnbr",
        config_flow.CONF_NAME: "prodnbr 2",
    }

    assert result["data"][config_flow.CONF_NAME] == "prodnbr 2"


async def test_zeroconf_flow(hass):
    """Test that zeroconf discovery for new devices work."""
    with patch.object(axis, "get_device", return_value=mock_coro(Mock())):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            data={
                config_flow.CONF_HOST: "1.2.3.4",
                config_flow.CONF_PORT: 80,
                "hostname": "name",
                "properties": {"macaddress": MAC},
            },
            context={"source": "zeroconf"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("axis.AxisDevice") as mock_device:

        setup_mock_axis_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_HOST: "1.2.3.4",
                config_flow.CONF_USERNAME: "user",
                config_flow.CONF_PASSWORD: "pass",
                config_flow.CONF_PORT: 80,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == f"prodnbr - {MAC}"
    assert result["data"] == {
        config_flow.CONF_HOST: "1.2.3.4",
        config_flow.CONF_USERNAME: "user",
        config_flow.CONF_PASSWORD: "pass",
        config_flow.CONF_PORT: 80,
        config_flow.CONF_MAC: MAC,
        config_flow.CONF_MODEL: "prodnbr",
        config_flow.CONF_NAME: "prodnbr 0",
    }

    assert result["data"][config_flow.CONF_NAME] == "prodnbr 0"


async def test_zeroconf_flow_already_configured(hass):
    """Test that zeroconf doesn't setup already configured devices."""
    device = await setup_axis_integration(hass)
    assert device.host == "1.2.3.4"

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            config_flow.CONF_HOST: "1.2.3.4",
            config_flow.CONF_PORT: 80,
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
        config_flow.CONF_HOST: "1.2.3.4",
        config_flow.CONF_PORT: 80,
        config_flow.CONF_USERNAME: "username",
        config_flow.CONF_PASSWORD: "password",
        config_flow.CONF_MAC: MAC,
        config_flow.CONF_MODEL: MODEL,
        config_flow.CONF_NAME: NAME,
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            config_flow.CONF_HOST: "2.3.4.5",
            config_flow.CONF_PORT: 8080,
            "hostname": "name",
            "properties": {"macaddress": MAC},
        },
        context={"source": "zeroconf"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert device.config_entry.data == {
        config_flow.CONF_HOST: "2.3.4.5",
        config_flow.CONF_PORT: 8080,
        config_flow.CONF_USERNAME: "username",
        config_flow.CONF_PASSWORD: "password",
        config_flow.CONF_MAC: MAC,
        config_flow.CONF_MODEL: MODEL,
        config_flow.CONF_NAME: NAME,
    }


async def test_zeroconf_flow_ignore_non_axis_device(hass):
    """Test that zeroconf doesn't setup devices with link local addresses."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            config_flow.CONF_HOST: "169.254.3.4",
            "properties": {"macaddress": "01234567890"},
        },
        context={"source": "zeroconf"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_axis_device"


async def test_zeroconf_flow_ignore_link_local_address(hass):
    """Test that zeroconf doesn't setup devices with link local addresses."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={config_flow.CONF_HOST: "169.254.3.4", "properties": {"macaddress": MAC}},
        context={"source": "zeroconf"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "link_local_address"
