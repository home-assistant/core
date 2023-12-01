"""Test the bangolufsen config_flow."""


from unittest.mock import Mock

from mozart_api.exceptions import ApiException, NotFoundException
import pytest
from urllib3.exceptions import MaxRetryError, NewConnectionError

from homeassistant.components.bangolufsen.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MockMozartClient
from .const import (
    TEST_DATA_CONFIRM,
    TEST_DATA_USER,
    TEST_DATA_USER_INVALID,
    TEST_DATA_ZEROCONF,
    TEST_DATA_ZEROCONF_NOT_MOZART,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_config_flow_max_retry_error(
    hass: HomeAssistant, mock_client: MockMozartClient
) -> None:
    """Test we handle not_mozart_device."""
    mock_client.get_beolink_self.side_effect = MaxRetryError(pool=Mock(), url="")

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER,
    )
    assert result_user["type"] == FlowResultType.ABORT
    assert result_user["reason"] == "max_retry_error"

    assert mock_client.get_beolink_self.call_count == 1
    assert mock_client.get_volume_settings.call_count == 0


async def test_config_flow_api_exception(
    hass: HomeAssistant, mock_client: MockMozartClient
) -> None:
    """Test we handle api_exception."""
    mock_client.get_beolink_self.side_effect = ApiException()

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER,
    )
    assert result_user["type"] == FlowResultType.ABORT
    assert result_user["reason"] == "api_exception"

    assert mock_client.get_beolink_self.call_count == 1
    assert mock_client.get_volume_settings.call_count == 0


async def test_config_flow_new_connection_error(
    hass: HomeAssistant, mock_client: MockMozartClient
) -> None:
    """Test we handle new_connection_error."""
    mock_client.get_beolink_self.side_effect = NewConnectionError(Mock(), "")

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER,
    )
    assert result_user["type"] == FlowResultType.ABORT
    assert result_user["reason"] == "new_connection_error"

    assert mock_client.get_beolink_self.call_count == 1
    assert mock_client.get_volume_settings.call_count == 0


async def test_config_flow_not_found_exception(
    hass: HomeAssistant,
    mock_client: MockMozartClient,
) -> None:
    """Test we handle not_found_exception."""
    mock_client.get_beolink_self.side_effect = NotFoundException()

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER,
    )
    assert result_user["type"] == FlowResultType.ABORT
    assert result_user["reason"] == "not_found_exception"

    assert mock_client.get_beolink_self.call_count == 1
    assert mock_client.get_volume_settings.call_count == 0


async def test_config_flow_value_error(hass: HomeAssistant) -> None:
    """Test we handle value_error."""

    result_init = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER_INVALID,
    )
    assert result_init["type"] == FlowResultType.ABORT
    assert result_init["reason"] == "value_error"


async def test_config_flow(
    hass: HomeAssistant, mock_client: MockMozartClient, mock_setup_entry
) -> None:
    """Test config flow."""

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=None,
    )

    assert result_user["type"] == FlowResultType.FORM
    assert result_user["step_id"] == "user"

    result_confirm = await hass.config_entries.flow.async_configure(
        flow_id=result_user["flow_id"],
        user_input=TEST_DATA_USER,
    )

    assert result_confirm["type"] == FlowResultType.FORM
    assert result_confirm["step_id"] == "confirm"

    result_entry = await hass.config_entries.flow.async_configure(
        flow_id=result_confirm["flow_id"],
        user_input=TEST_DATA_USER,
    )

    assert result_entry["type"] == FlowResultType.CREATE_ENTRY
    assert result_entry["data"] == TEST_DATA_CONFIRM

    assert mock_client.get_beolink_self.call_count == 1
    assert mock_client.get_volume_settings.call_count == 1


async def test_config_flow_zeroconf(
    hass: HomeAssistant, mock_client: MockMozartClient, mock_setup_entry
) -> None:
    """Test zeroconf discovery."""

    result_zeroconf = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DATA_ZEROCONF,
    )

    assert result_zeroconf["type"] == FlowResultType.FORM
    assert result_zeroconf["step_id"] == "confirm"

    result_confirm = await hass.config_entries.flow.async_configure(
        flow_id=result_zeroconf["flow_id"],
        user_input=TEST_DATA_USER,
    )

    assert result_confirm["type"] == FlowResultType.CREATE_ENTRY
    assert result_confirm["data"] == TEST_DATA_CONFIRM

    assert mock_client.get_beolink_self.call_count == 0
    assert mock_client.get_volume_settings.call_count == 1


async def test_config_flow_zeroconf_not_mozart_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery of invalid device."""

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DATA_ZEROCONF_NOT_MOZART,
    )

    assert result_user["type"] == FlowResultType.ABORT
    assert result_user["reason"] == "not_mozart_device"


# async def test_config_flow_options(hass: HomeAssistant, mock_config_entry) -> None:
#     """Test config flow options."""

#     mock_config_entry.add_to_hass(hass)

#     assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

#     result_user = await hass.config_entries.options.async_init(
#         mock_config_entry.entry_id
#     )

#     assert result_user["type"] == FlowResultType.FORM
#     assert result_user["step_id"] == "init"

#     result_confirm = await hass.config_entries.options.async_configure(
#         flow_id=result_user["flow_id"],
#         user_input=TEST_DATA_OPTIONS,
#     )

#     assert result_confirm["type"] == FlowResultType.CREATE_ENTRY
#     new_data = TEST_DATA_CONFIRM
#     new_data.update(TEST_DATA_OPTIONS)
#     assert result_confirm["data"] == new_data
