"""Test the DenonAVR config flow."""
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.denonavr.config_flow import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SERIAL_NUMBER,
    CONF_SHOW_ALL_SOURCES,
    CONF_TYPE,
    CONF_ZONE2,
    CONF_ZONE3,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_MAC

from tests.async_mock import patch
from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_MAC = "ab:cd:ef:gh"
TEST_HOST2 = "5.6.7.8"
TEST_NAME = "Test_Receiver"
TEST_MODEL = "model5"
TEST_RECEIVER_TYPE = "avr-x"
TEST_SERIALNUMBER = "123456789"
TEST_MANUFACTURER = "Denon"
TEST_SSDP_LOCATION = f"http://{TEST_HOST}/"
TEST_UNIQUE_ID = f"{TEST_MODEL}-{TEST_SERIALNUMBER}"
TEST_DISCOVER_1_RECEIVER = [{CONF_HOST: TEST_HOST}]
TEST_DISCOVER_2_RECEIVER = [{CONF_HOST: TEST_HOST}, {CONF_HOST: TEST_HOST2}]


@pytest.fixture(name="denonavr_connect", autouse=True)
def denonavr_connect_fixture():
    """Mock denonavr connection and entry setup."""
    with patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR._update_input_func_list",
        return_value=True,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR._get_receiver_name",
        return_value=TEST_NAME,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR._get_support_sound_mode",
        return_value=True,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR._update_avr_2016",
        return_value=True,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR._update_avr",
        return_value=True,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.get_device_info",
        return_value=True,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.name", TEST_NAME,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.model_name",
        TEST_MODEL,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.serial_number",
        TEST_SERIALNUMBER,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.manufacturer",
        TEST_MANUFACTURER,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.receiver_type",
        TEST_RECEIVER_TYPE,
    ), patch(
        "homeassistant.components.denonavr.config_flow.get_mac_address",
        return_value=TEST_MAC,
    ), patch(
        "homeassistant.components.denonavr.async_setup_entry", return_value=True
    ):
        yield


async def test_config_flow_manual_host_success(hass):
    """
    Successful flow manually initialized by the user.

    Host specified.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MAC: TEST_MAC,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
    }


async def test_config_flow_manual_discover_1_success(hass):
    """
    Successful flow manually initialized by the user.

    Without the host specified and 1 receiver discovered.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.config_flow.denonavr.ssdp.identify_denonavr_receivers",
        return_value=TEST_DISCOVER_1_RECEIVER,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MAC: TEST_MAC,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
    }


async def test_config_flow_manual_discover_2_success(hass):
    """
    Successful flow manually initialized by the user.

    Without the host specified and 2 receiver discovered.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.config_flow.denonavr.ssdp.identify_denonavr_receivers",
        return_value=TEST_DISCOVER_2_RECEIVER,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result["type"] == "form"
    assert result["step_id"] == "select"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"select_host": TEST_HOST2},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST2,
        CONF_MAC: TEST_MAC,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
    }


async def test_config_flow_manual_discover_error(hass):
    """
    Failed flow manually initialized by the user.

    Without the host specified and no receiver discovered.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.config_flow.denonavr.ssdp.identify_denonavr_receivers",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "discovery_error"}


async def test_config_flow_manual_host_no_serial(hass):
    """
    Successful flow manually initialized by the user.

    Host specified and an error getting the serial number.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.serial_number",
        None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MAC: TEST_MAC,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: None,
    }


async def test_config_flow_manual_host_no_mac(hass):
    """
    Successful flow manually initialized by the user.

    Host specified and an error getting the mac address.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.config_flow.get_mac_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MAC: None,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
    }


async def test_config_flow_manual_host_no_serial_no_mac(hass):
    """
    Successful flow manually initialized by the user.

    Host specified and an error getting the serial number and mac address.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.serial_number",
        None,
    ), patch(
        "homeassistant.components.denonavr.config_flow.get_mac_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MAC: None,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: None,
    }


async def test_config_flow_manual_host_no_serial_no_mac_exception(hass):
    """
    Successful flow manually initialized by the user.

    Host specified and an error getting the serial number and exception getting mac address.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.serial_number",
        None,
    ), patch(
        "homeassistant.components.denonavr.config_flow.get_mac_address",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MAC: None,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: None,
    }


async def test_config_flow_manual_host_connection_error(hass):
    """
    Failed flow manually initialized by the user.

    Host specified and a connection error.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.get_device_info",
        side_effect=ConnectionError,
    ), patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.receiver_type",
        None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "connection_error"


async def test_config_flow_manual_host_no_device_info(hass):
    """
    Failed flow manually initialized by the user.

    Host specified and no device info (due to receiver power off).
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.receiver_type",
        None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "connection_error"


async def test_config_flow_ssdp(hass):
    """Successful flow initialized by ssdp discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            ssdp.ATTR_UPNP_MANUFACTURER: TEST_MANUFACTURER,
            ssdp.ATTR_UPNP_MODEL_NAME: TEST_MODEL,
            ssdp.ATTR_UPNP_SERIAL: TEST_SERIALNUMBER,
            ssdp.ATTR_SSDP_LOCATION: TEST_SSDP_LOCATION,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MAC: TEST_MAC,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
    }


async def test_config_flow_ssdp_not_denon(hass):
    """
    Failed flow initialized by ssdp discovery.

    Not supported manufacturer.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            ssdp.ATTR_UPNP_MANUFACTURER: "NotSupported",
            ssdp.ATTR_UPNP_MODEL_NAME: TEST_MODEL,
            ssdp.ATTR_UPNP_SERIAL: TEST_SERIALNUMBER,
            ssdp.ATTR_SSDP_LOCATION: TEST_SSDP_LOCATION,
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_denonavr_manufacturer"


async def test_config_flow_ssdp_missing_info(hass):
    """
    Failed flow initialized by ssdp discovery.

    Missing information.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            ssdp.ATTR_UPNP_MANUFACTURER: TEST_MANUFACTURER,
            ssdp.ATTR_SSDP_LOCATION: TEST_SSDP_LOCATION,
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_denonavr_missing"


async def test_options_flow(hass):
    """Test specifying non default settings using options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={
            CONF_HOST: TEST_HOST,
            CONF_MAC: TEST_MAC,
            CONF_MODEL: TEST_MODEL,
            CONF_TYPE: TEST_RECEIVER_TYPE,
            CONF_MANUFACTURER: TEST_MANUFACTURER,
            CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
        },
        title=TEST_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SHOW_ALL_SOURCES: True, CONF_ZONE2: True, CONF_ZONE3: True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        CONF_SHOW_ALL_SOURCES: True,
        CONF_ZONE2: True,
        CONF_ZONE3: True,
    }


async def test_config_flow_manual_host_no_serial_double_config(hass):
    """
    Failed flow manually initialized by the user twice.

    Host specified and an error getting the serial number.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.serial_number",
        None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MAC: TEST_MAC,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: None,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR.serial_number",
        None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
