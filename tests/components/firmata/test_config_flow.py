"""Test the Firmata config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.firmata.const import CONF_SERIAL_PORT, DOMAIN
from homeassistant.core import HomeAssistant

from tests.async_mock import patch


async def test_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test we fail with an invalid board."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.firmata.board.get_board", side_effect=RuntimeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_SERIAL_PORT: "/dev/nonExistent"},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"
    await hass.async_block_till_done()


async def test_import(hass: HomeAssistant) -> None:
    """Test we create an entry from config."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    async def mock_get_board(config: dict):
        return MockPymata()

    class MockPymata:
        """A fake test board instance."""

        async def shutdown(self):
            """Shut down the fake board."""

    with patch(
        "homeassistant.components.firmata.config_flow.get_board",
        side_effect=mock_get_board,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_SERIAL_PORT: "/dev/nonExistent"},
        )

    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
