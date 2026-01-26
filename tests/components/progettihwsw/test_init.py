"""Test the ProgettiHWSW Automation init."""

from unittest.mock import patch

from homeassistant.components.progettihwsw.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_STATUS_XML = """
<response>
    <relay1>off</relay1>
    <relay2>on</relay2>
    <input1>up</input1>
    <input2>down</input2>
    <analog1>123</analog1>
</response>
"""


async def test_monkey_patch_logic(hass: HomeAssistant) -> None:
    """Test the monkey patch logic for get_states_by_tag_prefix."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: 80,
            "relay_count": 1,
            "input_count": 1,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.progettihwsw.ProgettiHWSWAPI.check_board",
            return_value=True,
        ),
        patch(
            "ProgettiHWSW.api.API.request",
            return_value=MOCK_STATUS_XML,
        ) as mock_request,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        api = hass.data[DOMAIN][entry.entry_id]

        # Test relay states (digital)
        states = await api.get_states_by_tag_prefix("relay")
        assert states
        assert states[1] is False  # off
        assert states[2] is True  # on

        # Test input states (digital)
        states = await api.get_states_by_tag_prefix("input")
        assert states
        assert states[1] is True  # up
        assert states[2] is False  # down

        # Test analog states
        states = await api.get_states_by_tag_prefix("analog", is_analog=True)
        assert states
        assert states[1] == "123"

        # Test empty/invalid response
        mock_request.return_value = False
        assert await api.get_states_by_tag_prefix("relay") is False

        # Test no matching tags
        mock_request.return_value = "<response></response>"
        assert await api.get_states_by_tag_prefix("relay") is False

        # Test hex parsing if applicable (though the code uses base 16 int conversion)
        # The code: number = int(i.tag[len(tag) :], 16)
        # If tag is "relay", and xml has <relayA>...</relayA>, A is 10.
        mock_request.return_value = "<response><relayA>on</relayA></response>"
        states = await api.get_states_by_tag_prefix("relay")
        assert states[10] is True
