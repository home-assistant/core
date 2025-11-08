"""Test the Switcher config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.switcher_kis.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_KEY,
    CONF_DEVICE_TYPE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .consts import (
    DUMMY_DUAL_SHUTTER_SINGLE_LIGHT_DEVICE,
    DUMMY_PLUG_DEVICE,
    DUMMY_SINGLE_SHUTTER_DUAL_LIGHT_DEVICE,
    DUMMY_TOKEN,
    DUMMY_USERNAME,
    DUMMY_WATER_HEATER_DEVICE,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "mock_bridge",
    [
        [
            DUMMY_PLUG_DEVICE,
            DUMMY_WATER_HEATER_DEVICE,
            # Make sure we don't detect the same device twice
            DUMMY_WATER_HEATER_DEVICE,
        ]
    ],
    indirect=True,
)
async def test_user_setup(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_bridge: MagicMock
) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch("homeassistant.components.switcher_kis.utils.DISCOVERY_TIME_SEC", 0):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discovery"}
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "confirm"

        result3 = await hass.config_entries.flow.async_configure(result2["flow_id"], {})

        assert mock_bridge.is_running is False
        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Switcher"
        assert result3["result"].data == {CONF_USERNAME: None, CONF_TOKEN: None}

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "mock_bridge",
    [
        [
            DUMMY_SINGLE_SHUTTER_DUAL_LIGHT_DEVICE,
            DUMMY_DUAL_SHUTTER_SINGLE_LIGHT_DEVICE,
        ]
    ],
    indirect=True,
)
async def test_user_setup_found_token_device_valid_token(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_bridge: MagicMock
) -> None:
    """Test we can finish a config flow with token device found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU

    with patch("homeassistant.components.switcher_kis.utils.DISCOVERY_TIME_SEC", 0):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discovery"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "confirm"

    result3 = await hass.config_entries.flow.async_configure(result2["flow_id"], {})

    assert mock_bridge.is_running is False
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "credentials"

    with patch(
        "homeassistant.components.switcher_kis.config_flow.validate_token",
        return_value=True,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {CONF_USERNAME: DUMMY_USERNAME, CONF_TOKEN: DUMMY_TOKEN},
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Switcher"
    assert result4["result"].data == {
        CONF_USERNAME: DUMMY_USERNAME,
        CONF_TOKEN: DUMMY_TOKEN,
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "mock_bridge",
    [
        [
            DUMMY_SINGLE_SHUTTER_DUAL_LIGHT_DEVICE,
            DUMMY_DUAL_SHUTTER_SINGLE_LIGHT_DEVICE,
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_bridge")
async def test_user_setup_found_token_device_invalid_token(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we can finish a config flow with token device found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU

    with patch("homeassistant.components.switcher_kis.utils.DISCOVERY_TIME_SEC", 0):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discovery"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "confirm"

    result3 = await hass.config_entries.flow.async_configure(result2["flow_id"], {})

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "credentials"

    with patch(
        "homeassistant.components.switcher_kis.config_flow.validate_token",
        return_value=False,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {CONF_USERNAME: DUMMY_USERNAME, CONF_TOKEN: DUMMY_TOKEN},
        )

    assert result4["type"] is FlowResultType.FORM
    assert result4["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.switcher_kis.config_flow.validate_token",
        return_value=True,
    ):
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {CONF_USERNAME: DUMMY_USERNAME, CONF_TOKEN: DUMMY_TOKEN},
        )

        assert result5["type"] is FlowResultType.CREATE_ENTRY
        assert result5["title"] == "Switcher"
        assert result5["result"].data == {
            CONF_USERNAME: DUMMY_USERNAME,
            CONF_TOKEN: DUMMY_TOKEN,
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_setup_abort_no_devices_found(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_bridge: MagicMock
) -> None:
    """Test we abort a config flow if no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU

    with patch("homeassistant.components.switcher_kis.utils.DISCOVERY_TIME_SEC", 0):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discovery"}
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "confirm"

        result3 = await hass.config_entries.flow.async_configure(result2["flow_id"], {})

        assert mock_bridge.is_running is False
        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "no_devices_found"

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0


async def test_manual_configuration_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual configuration with valid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "manual"

    with patch(
        "homeassistant.components.switcher_kis.config_flow.async_test_device_connection"
    ) as mock_test:
        mock_response = MagicMock()
        mock_response.successful = True
        mock_response.token_needed = False
        mock_test.return_value = mock_response

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_DEVICE_ID: "abc123",
                CONF_DEVICE_KEY: "1b",
                CONF_DEVICE_TYPE: "MINI",
            },
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Switcher"
    assert result3["result"].data == {
        CONF_USERNAME: None,
        CONF_TOKEN: None,
        CONF_HOST: "192.168.1.100",
        CONF_DEVICE_ID: "abc123",
        CONF_DEVICE_KEY: "1b",
        CONF_DEVICE_TYPE: "MINI",
    }


async def test_manual_configuration_cannot_connect(hass: HomeAssistant) -> None:
    """Test manual configuration with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    with patch(
        "homeassistant.components.switcher_kis.config_flow.async_test_device_connection",
        side_effect=TimeoutError("timeout"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_DEVICE_ID: "abc123",
                CONF_DEVICE_KEY: "1b",
                CONF_DEVICE_TYPE: "MINI",
            },
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_manual_configuration_invalid_auth(hass: HomeAssistant) -> None:
    """Test manual configuration with invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    with patch(
        "homeassistant.components.switcher_kis.config_flow.async_test_device_connection",
        side_effect=ValueError("invalid"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_DEVICE_ID: "abc123",
                CONF_DEVICE_KEY: "1b",
                CONF_DEVICE_TYPE: "MINI",
            },
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_manual_configuration_already_configured(hass: HomeAssistant) -> None:
    """Test manual configuration with already configured device."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="abc123",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_DEVICE_ID: "abc123",
            CONF_DEVICE_KEY: "1b",
            CONF_DEVICE_TYPE: "MINI",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    with patch(
        "homeassistant.components.switcher_kis.config_flow.async_test_device_connection"
    ) as mock_test:
        mock_response = MagicMock()
        mock_response.successful = True
        mock_response.token_needed = False
        mock_test.return_value = mock_response

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_DEVICE_ID: "abc123",
                CONF_DEVICE_KEY: "1b",
                CONF_DEVICE_TYPE: "MINI",
            },
        )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("user_input"),
    [
        ({CONF_USERNAME: DUMMY_USERNAME, CONF_TOKEN: DUMMY_TOKEN}),
    ],
)
async def test_reauth_successful(
    hass: HomeAssistant,
    user_input: dict[str, str],
) -> None:
    """Test starting a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: DUMMY_USERNAME, CONF_TOKEN: DUMMY_TOKEN},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.switcher_kis.config_flow.validate_token",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_invalid_auth(hass: HomeAssistant) -> None:
    """Test reauthentication flow with invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: DUMMY_USERNAME, CONF_TOKEN: DUMMY_TOKEN},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.switcher_kis.config_flow.validate_token",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "invalid_user", CONF_TOKEN: "invalid_token"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.switcher_kis.config_flow.validate_token",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_USERNAME: DUMMY_USERNAME, CONF_TOKEN: DUMMY_TOKEN},
        )

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "reauth_successful"
