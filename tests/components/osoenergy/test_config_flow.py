"""Test the OSO Energy config flow."""
from unittest.mock import patch

from apyosoenergyapi.helper import osoenergy_exceptions

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.osoenergy.const import DOMAIN, TITLE
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

SUBSCRIPTION_KEY = "valid subscription key"
SCAN_INTERVAL = 120
UPDATED_SCAN_INTERVAL = 60


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_devices",
        return_value=True,
    ), patch(
        "homeassistant.components.osoenergy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: SUBSCRIPTION_KEY},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == TITLE
    assert result2["data"] == {
        CONF_API_KEY: SUBSCRIPTION_KEY,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test the reauth flow."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TITLE,
        data={CONF_API_KEY: SUBSCRIPTION_KEY},
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_devices",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": mock_config.unique_id,
            },
            data=mock_config.data,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_devices",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: SUBSCRIPTION_KEY,
            },
        )
    await hass.async_block_till_done()

    assert mock_config.data.get(CONF_API_KEY) == SUBSCRIPTION_KEY
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_abort_if_existing_entry(hass: HomeAssistant) -> None:
    """Check flow abort when an entry already exist."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TITLE,
        data={CONF_API_KEY: SUBSCRIPTION_KEY},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_API_KEY: SUBSCRIPTION_KEY,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_invalid_subscription_key(hass: HomeAssistant) -> None:
    """Test user flow with invalid username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_devices",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: SUBSCRIPTION_KEY},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_flow_exception_on_subscription_key_check(
    hass: HomeAssistant,
) -> None:
    """Test user flow with invalid username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_devices",
        side_effect=osoenergy_exceptions.OSOEnergyReauthRequired(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: SUBSCRIPTION_KEY},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}
