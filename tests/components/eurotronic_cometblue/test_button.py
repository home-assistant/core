"""Test the eurotronic_cometblue button platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import setup_with_selected_platforms

from tests.common import MockConfigEntry


async def test_button_press_sync_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that pressing the sync-time button sets the device datetime."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.BUTTON])

    # Check if button is called correctly
    with patch.object(
        mock_config_entry.runtime_data.device,
        "set_datetime_async",
    ) as mock_set_datetime:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: "button.comet_blue_aa_bb_cc_dd_ee_ff_sync_time"},
            blocking=True,
        )

        mock_set_datetime.assert_called_once_with(date=dt_util.now())
