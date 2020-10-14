"""Test the Ruckus Unleashed DataUpdateCoordinator flow."""
from pyruckus import Ruckus

from homeassistant.components.ruckus_unleashed import (
    API_MAC,
    RuckusUnleashedDataUpdateCoordinator,
)
from homeassistant.components.ruckus_unleashed.const import (
    API_CLIENTS,
    API_CURRENT_ACTIVE_CLIENTS,
    API_NAME,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch
from tests.components.ruckus_unleashed import CONFIG, TEST_CLIENT


async def test_fetch_clients(hass):
    """Test we can fetch and transform clients."""
    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.connect",
        return_value=None,
    ), patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.current_active_clients",
        return_value={API_CURRENT_ACTIVE_CLIENTS: {API_CLIENTS: [TEST_CLIENT]}},
    ):
        ruckus = await hass.async_add_executor_job(
            Ruckus,
            CONFIG[CONF_HOST],
            CONFIG[CONF_USERNAME],
            CONFIG[CONF_PASSWORD],
        )

        coordinator = RuckusUnleashedDataUpdateCoordinator(hass, ruckus=ruckus)

        await coordinator.async_refresh()

    assert coordinator.data[API_CLIENTS]
    assert len(coordinator.data[API_CLIENTS]) == 1
    test_mac = TEST_CLIENT[API_MAC]
    assert coordinator.data[API_CLIENTS][test_mac][API_NAME] == TEST_CLIENT[API_NAME]
