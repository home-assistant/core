"""Test the Senziio config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.senziio.config_flow import CannotConnect
from homeassistant.components.senziio.entity import DOMAIN, MANUFACTURER
from homeassistant.components.senziio.exceptions import MQTTNotEnabled, RepeatedTitle
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_MODEL, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    A_DEVICE_ID,
    A_DEVICE_MODEL,
    A_FRIENDLY_NAME,
    ANOTHER_DEVICE_ID,
    DEVICE_INFO,
    ZEROCONF_DISCOVERY_INFO,
    FakeSenziioDevice,
)

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant):
    """Test a successful configuration via user initiated config flow."""
    with (
        patch(
            "homeassistant.components.senziio.config_flow.SenziioDevice",
            return_value=FakeSenziioDevice(DEVICE_INFO),
        ),
        patch(
            "homeassistant.components.senziio.async_setup_entry",
            return_value=True,
        ),
    ):
        # open user flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # check initialized form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # enter form data
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UNIQUE_ID: A_DEVICE_ID,
                CONF_MODEL: A_DEVICE_MODEL,
                CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
            },
        )

    # check expected data for entry creation
    expected_entry_data = {
        CONF_UNIQUE_ID: A_DEVICE_ID,
        CONF_MODEL: A_DEVICE_MODEL,
        CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
        "fw-version": "1.2.3",
        "hw-version": "1.0.0",
        "mac-address": "1A:2B:3C:4D:5E:6F",
        "serial-number": "theia-pro-2F3D56AA1234",
    }
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == A_FRIENDLY_NAME
    assert result2["data"] == expected_entry_data


@pytest.mark.parametrize(
    ("error", "expected_error_key"),
    [
        (MQTTNotEnabled, "mqtt_not_enabled"),
        (CannotConnect, "cannot_connect"),
        (RepeatedTitle, "repeated_title"),
        (KeyError, "unknown"),
        (RuntimeError, "unknown"),
        (Exception, "unknown"),
    ],
)
async def test_user_flow_form_error_handling(
    hass: HomeAssistant, error: Exception, expected_error_key: str
):
    """Test handling data errors in user config flow."""
    with patch(
        "homeassistant.components.senziio.config_flow.validate_input",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UNIQUE_ID: A_DEVICE_ID,
                CONF_MODEL: A_DEVICE_MODEL,
                CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
            },
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error_key}


async def test_user_flow_cannot_connect(hass: HomeAssistant):
    """Test raising connection error when no device data is retrieved."""
    with patch(
        "homeassistant.components.senziio.config_flow.SenziioDevice",
        return_value=FakeSenziioDevice({}),
    ):
        # open user flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # check initialized form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # enter form data
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UNIQUE_ID: A_DEVICE_ID,
                CONF_MODEL: A_DEVICE_MODEL,
                CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_aborted_if_device_id_already_configured(hass: HomeAssistant):
    """Test that the same friendly name can not be added twice via config flow."""
    with patch(
        "homeassistant.components.senziio.config_flow.SenziioDevice",
        return_value=FakeSenziioDevice(DEVICE_INFO),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=A_DEVICE_ID,
            title=A_FRIENDLY_NAME,
        )
        entry.add_to_hass(hass)

        # open user flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # enter form data with already used friendly name
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UNIQUE_ID: A_DEVICE_ID,
                CONF_MODEL: A_DEVICE_MODEL,
                CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
            },
        )

        assert result2["type"] == FlowResultType.ABORT


async def test_user_flow_repeated_friendly_name(hass: HomeAssistant):
    """Test that the same friendly name can not be added twice via config flow."""
    with patch(
        "homeassistant.components.senziio.config_flow.SenziioDevice",
        return_value=FakeSenziioDevice(DEVICE_INFO),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=A_DEVICE_ID,
            title=A_FRIENDLY_NAME,
        )
        entry.add_to_hass(hass)

        # open user flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # enter form data for different device with already used friendly name
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UNIQUE_ID: ANOTHER_DEVICE_ID,
                CONF_MODEL: A_DEVICE_MODEL,
                CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "repeated_title"}


async def test_user_flow_friendly_name_generation(hass: HomeAssistant):
    """Test that the same friendly name can not be added twice via config flow."""
    with patch(
        "homeassistant.components.senziio.config_flow.SenziioDevice",
        return_value=FakeSenziioDevice(DEVICE_INFO),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=A_DEVICE_ID,
            title=f"{MANUFACTURER} 2",
        )
        entry.add_to_hass(hass)

        # open user flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        proposed_friendly_name = next(
            field.default()
            for field in result["data_schema"].schema
            if field == "friendly_name"
        )

    assert proposed_friendly_name == f"{MANUFACTURER} 3"


async def test_zeroconf_flow_success(hass: HomeAssistant):
    """Test a successful configuration via zeroconf discovery."""
    with (
        patch(
            "homeassistant.components.senziio.config_flow.SenziioDevice",
            return_value=FakeSenziioDevice(DEVICE_INFO),
        ),
        patch(
            "homeassistant.components.senziio.async_setup_entry",
            return_value=True,
        ),
    ):
        # open zeroconf flow form
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY_INFO,
        )

        # check initialized form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "zeroconf_confirm"

        # enter form data
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
            },
        )

    # check expected data for entry creation
    expected_entry_data = {
        CONF_UNIQUE_ID: A_DEVICE_ID,
        CONF_MODEL: A_DEVICE_MODEL,
        CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
        "fw-version": "1.2.3",
        "hw-version": "1.0.0",
        "mac-address": "1A:2B:3C:4D:5E:6F",
        "serial-number": "theia-pro-2F3D56AA1234",
    }
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == A_FRIENDLY_NAME
    assert result2["data"] == expected_entry_data


@pytest.mark.parametrize(
    ("error", "expected_error_key"),
    [
        (MQTTNotEnabled, "mqtt_not_enabled"),
        (CannotConnect, "cannot_connect"),
        (RepeatedTitle, "repeated_title"),
        (KeyError, "unknown"),
        (RuntimeError, "unknown"),
        (Exception, "unknown"),
    ],
)
async def test_zeroconf_flow_form_error_handling(
    hass: HomeAssistant, error: Exception, expected_error_key: str
):
    """Test handling data errors in zeroconf config flow."""
    with patch(
        "homeassistant.components.senziio.config_flow.validate_input",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY_INFO,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
            },
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error_key}


async def test_zeroconf_flow_aborted_if_device_id_already_configured(
    hass: HomeAssistant,
):
    """Test that the same friendly name can not be added twice via config flow."""
    with patch(
        "homeassistant.components.senziio.config_flow.SenziioDevice",
        return_value=FakeSenziioDevice(DEVICE_INFO),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=A_DEVICE_ID,
            title=A_FRIENDLY_NAME,
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY_INFO,
        )

        # zerconf flow is not initiated
        assert result["type"] == FlowResultType.ABORT


async def test_zeroconf_flow_cannot_connect(hass: HomeAssistant):
    """Test raising connection error when no device data is retrieved."""
    with patch(
        "homeassistant.components.senziio.config_flow.SenziioDevice",
        return_value=FakeSenziioDevice({}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY_INFO,
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_flow_repeated_friendly_name(hass: HomeAssistant):
    """Test that the same friendly name can not be added twice via config flow."""
    with patch(
        "homeassistant.components.senziio.config_flow.SenziioDevice",
        return_value=FakeSenziioDevice(DEVICE_INFO),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=ANOTHER_DEVICE_ID,
            title=A_FRIENDLY_NAME,
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY_INFO,
        )

        # enter form data for different device with an already used friendly name
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "repeated_title"}
