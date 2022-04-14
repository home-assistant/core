"""Test the Remootio config flow."""
import logging
from unittest.mock import patch

from aioremootio import (
    RemootioClientAuthenticationError,
    RemootioClientConnectionEstablishmentError,
)

from homeassistant import config_entries
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.remootio.const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.components.remootio.exceptions import UnsupportedRemootioDeviceError
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

TDV_VALID_HOST = "127.0.0.1"
TDV_INVALID_HOST = "127.0.0_1"
TDV_VALID_CREDENTIAL = (
    "123456789A123456789B123456789C123456789D123456789E123456789FVXYZ"
)
TDV_INVALID_CREDENTIAL = "123456789A123456789B123456789C123456789D123456789E123456789F"
TDV_SERIAL_NUMBER = "1234567890"


async def test_form_unsupported_device(hass: HomeAssistant) -> None:
    """Tests the successful handling of the case if the client connects to an unsupported Remootio device."""

    with patch(
        "homeassistant.components.remootio.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.remootio.config_flow.get_serial_number",
        side_effect=UnsupportedRemootioDeviceError,
    ) as get_serial_number:
        init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_HOST: TDV_VALID_HOST,
                CONF_API_AUTH_KEY: TDV_VALID_CREDENTIAL,
                CONF_API_SECRET_KEY: TDV_VALID_CREDENTIAL,
                CONF_DEVICE_CLASS: CoverDeviceClass.GARAGE,
            },
        )

    _LOGGER.debug(f"init_result [{init_result}")
    assert init_result
    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["errors"] == {}

    _LOGGER.debug(f"configure_result [{configure_result}")
    assert configure_result
    assert configure_result["type"] == RESULT_TYPE_ABORT
    assert configure_result["reason"] == "unsupported_device"

    assert get_serial_number.called is True


async def test_form_invalid_user_input(hass: HomeAssistant) -> None:
    """Tests the successful handling of the case if the user input is invalid."""

    with patch(
        "homeassistant.components.remootio.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.remootio.config_flow.get_serial_number",
        return_value=TDV_SERIAL_NUMBER,
    ) as get_serial_number:
        init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_HOST: TDV_INVALID_HOST,
                CONF_API_AUTH_KEY: TDV_INVALID_CREDENTIAL,
                CONF_API_SECRET_KEY: TDV_VALID_CREDENTIAL,
                CONF_DEVICE_CLASS: CoverDeviceClass.GARAGE,
            },
        )

    _LOGGER.debug(f"init_result [{init_result}")
    assert init_result
    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["errors"] == {}

    _LOGGER.debug(f"configure_result [{configure_result}")
    assert configure_result
    assert configure_result["type"] == RESULT_TYPE_FORM
    assert configure_result["errors"] == {
        CONF_HOST: f"{CONF_HOST}_invalid",
        CONF_API_AUTH_KEY: f"{CONF_API_AUTH_KEY}_invalid",
    }

    assert get_serial_number.called is False


async def test_form_incomplete_user_input(hass: HomeAssistant) -> None:
    """Tests the successful handling of the case if the user input is invalid."""

    with patch(
        "homeassistant.components.remootio.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.remootio.config_flow.get_serial_number",
        return_value=TDV_SERIAL_NUMBER,
    ) as get_serial_number:
        init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_HOST: TDV_VALID_HOST,
                CONF_API_SECRET_KEY: TDV_VALID_CREDENTIAL,
                CONF_DEVICE_CLASS: CoverDeviceClass.GARAGE,
            },
        )

    _LOGGER.debug(f"init_result [{init_result}")
    assert init_result
    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["errors"] == {}

    _LOGGER.debug(f"configure_result [{configure_result}")
    assert configure_result
    assert configure_result["type"] == RESULT_TYPE_FORM
    assert configure_result["errors"] == {
        CONF_API_AUTH_KEY: f"{CONF_API_AUTH_KEY}_required"
    }

    assert get_serial_number.called is False


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Tests the successful handling of the case if the client cannot connect to the Remootio device."""

    with patch(
        "homeassistant.components.remootio.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.remootio.config_flow.get_serial_number",
        side_effect=RemootioClientConnectionEstablishmentError(None, None),
    ) as get_serial_number:
        init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_HOST: TDV_VALID_HOST,
                CONF_API_AUTH_KEY: TDV_VALID_CREDENTIAL,
                CONF_API_SECRET_KEY: TDV_VALID_CREDENTIAL,
                CONF_DEVICE_CLASS: CoverDeviceClass.GARAGE,
            },
        )

    _LOGGER.debug(f"init_result [{init_result}")
    assert init_result
    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["errors"] == {}

    _LOGGER.debug(f"configure_result [{configure_result}")
    assert configure_result
    assert configure_result["type"] == RESULT_TYPE_FORM
    assert configure_result["errors"] == {"base": "cannot_connect"}

    assert get_serial_number.called is True


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Tests the successful handling of the case if the client cannot authenticate itself to the Remootio device."""

    with patch(
        "homeassistant.components.remootio.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.remootio.config_flow.get_serial_number",
        side_effect=RemootioClientAuthenticationError(None, None),
    ) as get_serial_number:
        init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_HOST: TDV_VALID_HOST,
                CONF_API_AUTH_KEY: TDV_VALID_CREDENTIAL,
                CONF_API_SECRET_KEY: TDV_VALID_CREDENTIAL,
                CONF_DEVICE_CLASS: CoverDeviceClass.GARAGE,
            },
        )

    _LOGGER.debug(f"init_result [{init_result}")
    assert init_result
    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["errors"] == {}

    _LOGGER.debug(f"configure_result [{configure_result}")
    assert configure_result
    assert configure_result["type"] == RESULT_TYPE_FORM
    assert configure_result["errors"] == {"base": "invalid_auth"}

    assert get_serial_number.called is True


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Tests the successful handling of the case if the Remootio device is already configured."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TDV_VALID_HOST,
            CONF_API_SECRET_KEY: TDV_VALID_CREDENTIAL,
            CONF_API_AUTH_KEY: TDV_VALID_CREDENTIAL,
            CONF_DEVICE_CLASS: CoverDeviceClass.GARAGE,
            CONF_SERIAL_NUMBER: TDV_SERIAL_NUMBER,
        },
        unique_id=TDV_SERIAL_NUMBER,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.remootio.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.remootio.config_flow.get_serial_number",
        return_value=TDV_SERIAL_NUMBER,
    ) as get_serial_number:
        init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_HOST: TDV_VALID_HOST,
                CONF_API_AUTH_KEY: TDV_VALID_CREDENTIAL,
                CONF_API_SECRET_KEY: TDV_VALID_CREDENTIAL,
                CONF_DEVICE_CLASS: CoverDeviceClass.GARAGE,
            },
        )

    _LOGGER.debug(f"init_result [{init_result}")
    assert init_result
    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["errors"] == {}

    _LOGGER.debug(f"configure_result [{configure_result}")
    assert configure_result
    assert configure_result["type"] == RESULT_TYPE_ABORT
    assert configure_result["reason"] == "already_configured"

    assert get_serial_number.called is True


async def test_form(hass: HomeAssistant) -> None:
    """Tests the successful handling of the case if the Remootio device can be successfully configured."""

    with patch(
        "homeassistant.components.remootio.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.remootio.config_flow.get_serial_number",
        return_value=TDV_SERIAL_NUMBER,
    ) as get_serial_number:
        init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_HOST: TDV_VALID_HOST,
                CONF_API_AUTH_KEY: TDV_VALID_CREDENTIAL,
                CONF_API_SECRET_KEY: TDV_VALID_CREDENTIAL,
                CONF_DEVICE_CLASS: CoverDeviceClass.GARAGE,
            },
        )

    _LOGGER.debug(f"init_result [{init_result}")
    assert init_result
    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["errors"] == {}

    _LOGGER.debug(f"configure_result [{configure_result}")
    assert configure_result
    assert configure_result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert configure_result["data"] == {
        CONF_HOST: TDV_VALID_HOST,
        CONF_API_AUTH_KEY: TDV_VALID_CREDENTIAL,
        CONF_API_SECRET_KEY: TDV_VALID_CREDENTIAL,
        CONF_DEVICE_CLASS: CoverDeviceClass.GARAGE,
        CONF_SERIAL_NUMBER: TDV_SERIAL_NUMBER,
    }

    assert get_serial_number.called is True
