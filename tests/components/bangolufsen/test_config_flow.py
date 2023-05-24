"""Test the bangolufsen config_flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.bangolufsen.const import (
    API_EXCEPTION,
    DOMAIN,
    MAX_RETRY_ERROR,
    NEW_CONNECTION_ERROR,
    NOT_MOZART_DEVICE,
    VALUE_ERROR,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MockMozartClient as mmc, TestConstantsConfigFlow as tc
from .util import mock_entry


async def test_config_flow_max_retry_error(hass: HomeAssistant) -> None:
    """Test we handle not_mozart_device."""
    result_init = await hass.config_entries.flow.async_init(
        handler=DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_init["type"] == FlowResultType.FORM
    assert result_init["step_id"] == "user"

    client = mmc()

    with patch(
        client.methods.get_beolink_self, return_value=client.methods.async_result()
    ), patch(client.methods.get_result, side_effect=client.max_retry_error):
        result_configure = await hass.config_entries.flow.async_configure(
            flow_id=result_init["flow_id"],
            user_input=tc.TEST_DATA_ONLY_HOST,
        )

    assert result_configure["type"] == FlowResultType.ABORT
    assert result_configure["reason"] == MAX_RETRY_ERROR


async def test_config_flow_api_exception(hass: HomeAssistant) -> None:
    """Test we handle api_exception."""

    result_init = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result_init["type"] == FlowResultType.FORM
    assert result_init["step_id"] == "user"

    client = mmc()

    with patch(
        client.methods.get_beolink_self, return_value=client.methods.async_result()
    ), patch(client.methods.get_result, side_effect=client.api_exception):
        result_configure = await hass.config_entries.flow.async_configure(
            flow_id=result_init["flow_id"],
            user_input=tc.TEST_DATA_ONLY_HOST,
        )

    assert result_configure["type"] == FlowResultType.ABORT
    assert result_configure["reason"] == API_EXCEPTION


async def test_config_flow_new_connection_error(hass: HomeAssistant) -> None:
    """Test we handle new_connection_error."""

    result_init = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result_init["type"] == FlowResultType.FORM
    assert result_init["step_id"] == "user"

    client = mmc()

    with patch(
        client.methods.get_beolink_self, return_value=client.methods.async_result()
    ), patch(client.methods.get_result, side_effect=client.new_connection_error):
        result_configure = await hass.config_entries.flow.async_configure(
            flow_id=result_init["flow_id"],
            user_input=tc.TEST_DATA_ONLY_HOST,
        )

    assert result_configure["type"] == FlowResultType.ABORT
    assert result_configure["reason"] == NEW_CONNECTION_ERROR


async def test_config_flow_value_error(hass: HomeAssistant) -> None:
    """Test we handle value_error."""

    result_init = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result_init["type"] == FlowResultType.FORM
    assert result_init["step_id"] == "user"

    result_configure = await hass.config_entries.flow.async_configure(
        flow_id=result_init["flow_id"],
        user_input=tc.TEST_DATA_ONLY_HOST_INVALID,
    )

    assert result_configure["type"] == FlowResultType.ABORT
    assert result_configure["reason"] == VALUE_ERROR


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test config flow."""
    result_init = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result_init["type"] == FlowResultType.FORM
    assert result_init["step_id"] == "user"

    client = mmc()

    with patch(
        client.methods.get_beolink_self, return_value=client.methods.async_result()
    ), patch(
        client.methods.get_volume_settings, return_value=client.methods.async_result()
    ), patch(
        client.methods.get_result,
        side_effect=[mmc.Get.get_beolink_self, mmc.Get.get_volume_settings],
    ), patch(
        tc.SETUP_ENTRY, return_value=True
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            flow_id=result_init["flow_id"],
            user_input=tc.TEST_DATA_ONLY_HOST,
        )

        assert result_configure["type"] == FlowResultType.FORM
        assert result_configure["step_id"] == "confirm"

        result_configure_final = await hass.config_entries.flow.async_configure(
            flow_id=result_configure["flow_id"],
            user_input=tc.TEST_DATA_NO_HOST,
        )

    assert result_configure_final["type"] == FlowResultType.CREATE_ENTRY
    assert result_configure_final["data"] == tc.TEST_DATA_FULL


async def test_config_flow_zeroconf(hass: HomeAssistant) -> None:
    """Test zeroconf discovery."""

    client = mmc()

    with patch(
        client.methods.get_volume_settings, return_value=client.methods.async_result()
    ), patch(
        client.methods.get_result,
        side_effect=[mmc.Get.get_volume_settings],
    ), patch(
        tc.SETUP_ENTRY, return_value=True
    ):
        result_init = await hass.config_entries.flow.async_init(
            handler=DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=tc.TEST_DATA_ZEROCONF,
        )

        assert result_init["type"] == FlowResultType.FORM
        assert result_init["step_id"] == "confirm"

        result_configure = await hass.config_entries.flow.async_configure(
            flow_id=result_init["flow_id"],
            user_input=tc.TEST_DATA_NO_HOST,
        )

    assert result_configure["type"] == FlowResultType.CREATE_ENTRY
    assert result_configure["data"] == tc.TEST_DATA_FULL


async def test_config_flow_zeroconf_not_mozart_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery of invalid device."""

    result_init = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=tc.TEST_DATA_ZEROCONF_NOT_MOZART,
    )

    assert result_init["type"] == FlowResultType.ABORT
    assert result_init["reason"] == NOT_MOZART_DEVICE


async def test_config_flow_options(hass: HomeAssistant) -> None:
    """Test config flow options."""

    config_entry = mock_entry()

    config_entry.add_to_hass(hass)

    client = mmc()

    with patch(
        client.methods.get_volume_settings, return_value=client.methods.async_result()
    ), patch(
        client.methods.get_result, side_effect=[mmc.Get.get_volume_settings]
    ), patch(
        tc.SETUP_ENTRY, return_value=True
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        result_init = await hass.config_entries.options.async_init(
            config_entry.entry_id
        )

        assert result_init["type"] == FlowResultType.FORM
        assert result_init["step_id"] == "init"

        result_configure = await hass.config_entries.options.async_configure(
            flow_id=result_init["flow_id"],
            user_input=tc.TEST_DATA_OPTIONS,
        )

        assert result_configure["type"] == FlowResultType.CREATE_ENTRY
        new_data = tc.TEST_DATA_FULL
        new_data.update(tc.TEST_DATA_OPTIONS)
        assert result_configure["data"] == new_data
