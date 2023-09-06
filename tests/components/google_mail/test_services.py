"""Services tests for the Google Mail integration."""
from unittest.mock import patch

from google.auth.exceptions import RefreshError
import pytest

from homeassistant import config_entries
from homeassistant.components.google_mail import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import BUILD, SENSOR, TOKEN, ComponentSetup


async def test_set_vacation(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test service call set vacation."""
    await setup_integration()

    with patch(BUILD) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "set_vacation",
            {
                "entity_id": SENSOR,
                "enabled": True,
                "title": "Vacation",
                "message": "Vacation message",
                "plain_text": False,
                "restrict_contacts": True,
                "restrict_domain": True,
                "start": "2022-11-20",
                "end": "2022-11-26",
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 5

    with patch(BUILD) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "set_vacation",
            {
                "entity_id": SENSOR,
                "enabled": True,
                "title": "Vacation",
                "message": "Vacation message",
                "plain_text": True,
                "restrict_contacts": True,
                "restrict_domain": True,
                "start": "2022-11-20",
                "end": "2022-11-26",
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 5


async def test_reauth_trigger(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test reauth is triggered after a refresh error during service call."""
    await setup_integration()

    with patch(TOKEN, side_effect=RefreshError), pytest.raises(RefreshError):
        await hass.services.async_call(
            DOMAIN,
            "set_vacation",
            {
                "entity_id": SENSOR,
                "enabled": True,
                "title": "Vacation",
                "message": "Vacation message",
                "plain_text": True,
                "restrict_contacts": True,
                "restrict_domain": True,
                "start": "2022-11-20",
                "end": "2022-11-26",
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
