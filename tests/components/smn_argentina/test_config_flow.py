"""Test the SMN config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.smn_argentina.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

COMMON_IGNORES = []


@pytest.fixture
def ignore_missing_translations(request: pytest.FixtureRequest) -> list[str]:
    """Ignore missing translations."""
    ignores = COMMON_IGNORES.copy()
    if hasattr(request, "param"):
        ignores.extend(request.param)
    return ignores


@pytest.mark.asyncio
async def test_form_home_location(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test we can configure with home location coordinates."""
    # Set home location
    hass.config.latitude = -34.6217
    hass.config.longitude = -58.4258

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.smn_argentina.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LATITUDE: -34.6217,
                CONF_LONGITUDE: -58.4258,
                CONF_NAME: "My Home",
            },
        )

        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "My Home"
        assert result2["data"] == {
            CONF_LATITUDE: -34.6217,
            CONF_LONGITUDE: -58.4258,
            CONF_NAME: "My Home",
        }


@pytest.mark.asyncio
async def test_form_custom_location(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test we can configure with custom location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.smn_argentina.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LATITUDE: -31.4201,
                CONF_LONGITUDE: -64.1888,
                CONF_NAME: "Córdoba",
            },
        )

        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Córdoba"
        assert result2["data"] == {
            CONF_LATITUDE: -31.4201,
            CONF_LONGITUDE: -64.1888,
            CONF_NAME: "Córdoba",
        }


@pytest.mark.asyncio
async def test_form_already_configured(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test we handle already configured."""
    # Create an existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Buenos Aires",
        data={
            CONF_LATITUDE: -34.6217,
            CONF_LONGITUDE: -58.4258,
            CONF_NAME: "Buenos Aires",
        },
        unique_id="-34.6217--58.4258",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LATITUDE: -34.6217,
            CONF_LONGITUDE: -58.4258,
            CONF_NAME: "Another Name",
        },
    )

    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_form_api_error(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test config flow succeeds even if API has errors (they're handled during refresh)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    # Make the API client raise an error (this will happen during first refresh, not during config)
    mock_smn_api_client.async_get_location.side_effect = Exception("API Error")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LATITUDE: -31.4201,
            CONF_LONGITUDE: -64.1888,
            CONF_NAME: "Test Location",
        },
    )

    await hass.async_block_till_done()

    # Config flow creates the entry successfully
    # The API error will be handled during the first coordinator refresh
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Location"
