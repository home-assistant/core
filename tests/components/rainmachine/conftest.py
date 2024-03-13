"""Define test fixtures for RainMachine."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.rainmachine import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="client")
def client_fixture(controller, controller_mac):
    """Define a regenmaschine client."""
    return AsyncMock(load_local=AsyncMock(), controllers={controller_mac: controller})


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, controller_mac):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=controller_mac, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="controller")
def controller_fixture(
    controller_mac,
    data_api_versions,
    data_diagnostics_current,
    data_machine_firmare_update_status,
    data_programs,
    data_provision_settings,
    data_restrictions_current,
    data_restrictions_universal,
    data_zones,
):
    """Define a regenmaschine controller."""
    controller = AsyncMock()
    controller.api_version = "4.5.0"
    controller.hardware_version = "3"
    controller.name = "12345"
    controller.mac = controller_mac
    controller.software_version = "4.0.925"

    controller.api.versions.return_value = data_api_versions
    controller.diagnostics.current.return_value = data_diagnostics_current
    controller.machine.get_firmware_update_status.return_value = (
        data_machine_firmare_update_status
    )
    controller.programs.all.return_value = data_programs
    controller.provisioning.settings.return_value = data_provision_settings
    controller.restrictions.current.return_value = data_restrictions_current
    controller.restrictions.universal.return_value = data_restrictions_universal
    controller.zones.all.return_value = data_zones

    return controller


@pytest.fixture(name="controller_mac")
def controller_mac_fixture():
    """Define a controller MAC address."""
    return "aa:bb:cc:dd:ee:ff"


@pytest.fixture(name="data_api_versions", scope="package")
def data_api_versions_fixture():
    """Define API version data."""
    return json.loads(load_fixture("api_versions_data.json", "rainmachine"))


@pytest.fixture(name="data_diagnostics_current", scope="package")
def data_diagnostics_current_fixture():
    """Define current diagnostics data."""
    return json.loads(load_fixture("diagnostics_current_data.json", "rainmachine"))


@pytest.fixture(name="data_machine_firmare_update_status", scope="package")
def data_machine_firmare_update_status_fixture():
    """Define machine firmware update status data."""
    return json.loads(
        load_fixture("machine_firmware_update_status_data.json", "rainmachine")
    )


@pytest.fixture(name="data_programs", scope="package")
def data_programs_fixture():
    """Define program data."""
    return json.loads(load_fixture("programs_data.json", "rainmachine"))


@pytest.fixture(name="data_provision_settings", scope="package")
def data_provision_settings_fixture():
    """Define provisioning settings data."""
    return json.loads(load_fixture("provision_settings_data.json", "rainmachine"))


@pytest.fixture(name="data_restrictions_current", scope="package")
def data_restrictions_current_fixture():
    """Define current restrictions settings data."""
    return json.loads(load_fixture("restrictions_current_data.json", "rainmachine"))


@pytest.fixture(name="data_restrictions_universal", scope="package")
def data_restrictions_universal_fixture():
    """Define universal restrictions settings data."""
    return json.loads(load_fixture("restrictions_universal_data.json", "rainmachine"))


@pytest.fixture(name="data_zones", scope="package")
def data_zones_fixture():
    """Define zone data."""
    return json.loads(load_fixture("zones_data.json", "rainmachine"))


@pytest.fixture(name="setup_rainmachine")
async def setup_rainmachine_fixture(hass, client, config):
    """Define a fixture to set up RainMachine."""
    with patch(
        "homeassistant.components.rainmachine.Client", return_value=client
    ), patch(
        "homeassistant.components.rainmachine.config_flow.Client", return_value=client
    ), patch(
        "homeassistant.components.rainmachine.PLATFORMS",
        [],
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield
