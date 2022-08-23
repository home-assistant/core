"""Test the MPRIS media playback remote control config flow."""
from unittest.mock import patch

import pskca

from homeassistant import config_entries
from homeassistant.components.hassmpris.const import DOMAIN, STEP_CONFIRM
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


class MockECDH:
    """Mock ECDH."""

    derived_key = b"012345678901234567890123456789"


class MockCakesClient:
    """Mock CAKES client."""

    async def obtain_verifier(self):
        """Fake verifier."""
        return MockECDH()

    async def obtain_certificate(self):
        """Fake certificate."""
        # Any silly certificate will do, so we make one.
        cert = pskca.create_certificate_and_key()[0]
        return cert, [cert]


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test we get the user form and, upon success, go to confirm step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert not result["errors"]

    with patch("hassmpris_client.AsyncCAKESClient", return_value=MockCakesClient()):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == STEP_CONFIRM

    with patch(
        "homeassistant.components.hassmpris.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "hassmpris_client.AsyncCAKESClient", return_value=MockCakesClient()
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "emojis": "doesn't matter",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


# Possible additional tests:
#
# * test what happens when the user rejects the match
# * test what happens when the other side rejects the match
# * test what happens when cannot connect to CAKES
