"""Test the homewizard energy config flow."""
from unittest.mock import AsyncMock, Mock, patch

from homeassistant import config_entries
from homeassistant.components.homewizard_energy.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS


def get_mock_device(
    serial="aabbccddeeff", host="1.2.3.4", product_name="P1", product_type="HWE-P1"
):
    """Return a mock bridge."""
    mock_device = Mock()
    mock_device._host = host

    mock_device.device.product_name = product_name
    mock_device.device.product_type = product_type
    mock_device.device.serial = serial
    mock_device.device.api_version = "v1"
    mock_device.device.firmware_version = "1.00"

    mock_device.initialize = AsyncMock()
    mock_device.close = AsyncMock()

    return mock_device


async def test_manual_flow_works(hass, aioclient_mock):
    """Test config flow accepts user configuration."""

    device = get_mock_device()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.homewizard_energy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "CustomName"}
        )

    assert result["title"] == f"{device.device.product_name} (CustomName)"
    assert result["data"]["host"] == "2.2.2.2"
    assert (
        result["data"]["unique_id"]
        == f"{device.device.product_type}_{device.device.serial}"
    )
    assert result["data"]["product_name"] == device.device.product_name
    assert result["data"]["product_type"] == device.device.product_type
    assert result["data"]["serial"] == device.device.serial

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        entries = hass.config_entries.async_entries(DOMAIN)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.unique_id == f"{device.device.product_type}_{device.device.serial}"

    assert len(device.initialize.mock_calls) == 1
    assert len(device.close.mock_calls) == 1


# async def test_config_flow_already_configured_weather(hass):
#     """Test already configured."""
#     entry = MockConfigEntry(
#         domain=DOMAIN,
#         unique_id=f"HWE_P1_aabccddeeff",
#     )
#     entry.add_to_hass(hass)

#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     assert result["type"] == "form"
#     assert result["step_id"] == "user"
#     assert result["errors"] == {}

#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE},
#     )

#     assert result["type"] == "abort"
#     assert result["reason"] == "already_configured"


# async def test_options_flow(hass):
#     """Test options flow."""
#     entry = MockConfigEntry(
#         domain=DOMAIN,
#         data={
#             CONF_LATITUDE: TEST_LATITUDE,
#             CONF_LONGITUDE: TEST_LONGITUDE,
#         },
#         unique_id=DOMAIN,
#     )
#     entry.add_to_hass(hass)

#     await hass.config_entries.async_setup(entry.entry_id)
#     await hass.async_block_till_done()

#     result = await hass.config_entries.options.async_init(entry.entry_id)

#     assert result["type"] == "form"
#     assert result["step_id"] == "init"

#     result = await hass.config_entries.options.async_configure(
#         result["flow_id"],
#         user_input={"country_code": "BE", "delta": 450, "timeframe": 30},
#     )

#     with patch(
#         "homeassistant.components.buienradar.async_setup_entry", return_value=True
#     ), patch(
#         "homeassistant.components.buienradar.async_unload_entry", return_value=True
#     ):
#         assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

#         await hass.async_block_till_done()

#     assert entry.options == {"country_code": "BE", "delta": 450, "timeframe": 30}
