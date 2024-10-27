"""Test the OSO Energy config flow."""

from unittest.mock import patch

from apyosoenergyapi.helper import osoenergy_exceptions

from homeassistant import config_entries
from homeassistant.components.osoenergy.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

SUBSCRIPTION_KEY = "valid subscription key"
SCAN_INTERVAL = 120
TEST_USER_EMAIL = "test_user_email@domain.com"
UPDATED_SCAN_INTERVAL = 60


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_user_email",
            return_value=TEST_USER_EMAIL,
        ),
        patch(
            "homeassistant.components.osoenergy.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: SUBSCRIPTION_KEY},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_USER_EMAIL
    assert result2["data"] == {
        CONF_API_KEY: SUBSCRIPTION_KEY,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test the reauth flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USER_EMAIL,
        data={CONF_API_KEY: SUBSCRIPTION_KEY},
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_user_email",
        return_value=None,
    ):
        result = await mock_config.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_user_email",
        return_value=TEST_USER_EMAIL,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: SUBSCRIPTION_KEY,
            },
        )
    await hass.async_block_till_done()

    assert mock_config.data.get(CONF_API_KEY) == SUBSCRIPTION_KEY
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_abort_if_existing_entry(hass: HomeAssistant) -> None:
    """Check flow abort when an entry already exist."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USER_EMAIL,
        data={CONF_API_KEY: SUBSCRIPTION_KEY},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_user_email",
        return_value=TEST_USER_EMAIL,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_API_KEY: SUBSCRIPTION_KEY,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_invalid_subscription_key(hass: HomeAssistant) -> None:
    """Test user flow with invalid username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_user_email",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: SUBSCRIPTION_KEY},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_flow_exception_on_subscription_key_check(
    hass: HomeAssistant,
) -> None:
    """Test user flow with invalid username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.osoenergy.config_flow.OSOEnergy.get_user_email",
        side_effect=osoenergy_exceptions.OSOEnergyReauthRequired(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: SUBSCRIPTION_KEY},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}
