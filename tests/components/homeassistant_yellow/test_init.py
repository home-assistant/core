"""Test the Home Assistant Yellow integration."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components import zha
from homeassistant.components.hassio import DOMAIN as HASSIO_DOMAIN
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.homeassistant_yellow.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration


@pytest.fixture(autouse=True)
def mock_async_validate_hardware_consistent():
    """Mock validate hardware state."""
    with patch(
        "homeassistant.components.homeassistant_yellow.async_validate_hardware_consistent",
        return_value=True,
    ):
        yield


@pytest.mark.parametrize(
    ("onboarded", "num_entries", "num_flows"), [(False, 1, 0), (True, 0, 1)]
)
async def test_setup_entry(
    hass: HomeAssistant, onboarded, num_entries, num_flows, addon_store_info
) -> None:
    """Test setup of a config entry, including setup of zha."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ) as mock_get_os_info,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=onboarded,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_get_os_info.mock_calls) == 1

    # Finish setting up ZHA
    if num_entries > 0:
        zha_flows = hass.config_entries.flow.async_progress_by_handler("zha")
        assert len(zha_flows) == 1
        assert zha_flows[0]["step_id"] == "choose_formation_strategy"

        await hass.config_entries.flow.async_configure(
            zha_flows[0]["flow_id"],
            user_input={"next_step_id": zha.config_flow.FORMATION_REUSE_SETTINGS},
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress_by_handler("zha")) == num_flows
    assert len(hass.config_entries.async_entries("zha")) == num_entries

    # Test unloading the config entry
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_setup_zha(hass: HomeAssistant, addon_store_info) -> None:
    """Test zha gets the right config."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ) as mock_get_os_info,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded", return_value=False
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(mock_get_os_info.mock_calls) == 1

    # Finish setting up ZHA
    zha_flows = hass.config_entries.flow.async_progress_by_handler("zha")
    assert len(zha_flows) == 1
    assert zha_flows[0]["step_id"] == "choose_formation_strategy"

    await hass.config_entries.flow.async_configure(
        zha_flows[0]["flow_id"],
        user_input={"next_step_id": zha.config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries("zha")[0]
    assert config_entry.data == {
        "device": {
            "baudrate": 115200,
            "flow_control": "hardware",
            "path": "/dev/ttyAMA1",
        },
        "radio_type": "ezsp",
    }
    assert config_entry.options == {}
    assert config_entry.title == "Yellow"


async def test_setup_zha_multipan(
    hass: HomeAssistant, addon_info, addon_running
) -> None:
    """Test zha gets the right config."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    addon_info.return_value["options"]["device"] = "/dev/ttyAMA1"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ) as mock_get_os_info,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded", return_value=False
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(mock_get_os_info.mock_calls) == 1

    # Finish setting up ZHA
    zha_flows = hass.config_entries.flow.async_progress_by_handler("zha")
    assert len(zha_flows) == 1
    assert zha_flows[0]["step_id"] == "choose_formation_strategy"

    await hass.config_entries.flow.async_configure(
        zha_flows[0]["flow_id"],
        user_input={"next_step_id": zha.config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries("zha")[0]
    assert config_entry.data == {
        "device": {
            "baudrate": 115200,
            "flow_control": None,
            "path": "socket://core-silabs-multiprotocol:9999",
        },
        "radio_type": "ezsp",
    }
    assert config_entry.options == {}
    assert config_entry.title == "Yellow Multiprotocol"


async def test_setup_zha_multipan_other_device(
    hass: HomeAssistant, addon_info, addon_running
) -> None:
    """Test zha gets the right config."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    addon_info.return_value["options"]["device"] = "/dev/not_yellow_radio"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ) as mock_get_os_info,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded", return_value=False
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(mock_get_os_info.mock_calls) == 1

    # Finish setting up ZHA
    zha_flows = hass.config_entries.flow.async_progress_by_handler("zha")
    assert len(zha_flows) == 1
    assert zha_flows[0]["step_id"] == "choose_formation_strategy"

    await hass.config_entries.flow.async_configure(
        zha_flows[0]["flow_id"],
        user_input={"next_step_id": zha.config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries("zha")[0]
    assert config_entry.data == {
        "device": {
            "baudrate": 115200,
            "flow_control": "hardware",
            "path": "/dev/ttyAMA1",
        },
        "radio_type": "ezsp",
    }
    assert config_entry.options == {}
    assert config_entry.title == "Yellow"


async def test_setup_entry_no_hassio(hass: HomeAssistant) -> None:
    """Test setup of a config entry without hassio."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries()) == 1

    with patch(
        "homeassistant.components.homeassistant_yellow.get_os_info"
    ) as mock_get_os_info:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(mock_get_os_info.mock_calls) == 0
    assert len(hass.config_entries.async_entries()) == 0


async def test_setup_entry_wrong_board(hass: HomeAssistant) -> None:
    """Test setup of a config entry with wrong board type."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries()) == 1

    with patch(
        "homeassistant.components.homeassistant_yellow.get_os_info",
        return_value={"board": "generic-x86-64"},
    ) as mock_get_os_info:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(mock_get_os_info.mock_calls) == 1
    assert len(hass.config_entries.async_entries()) == 0


async def test_setup_entry_wait_hassio(hass: HomeAssistant) -> None:
    """Test setup of a config entry when hassio has not fetched os_info."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.homeassistant_yellow.get_os_info",
        return_value=None,
    ) as mock_get_os_info:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(mock_get_os_info.mock_calls) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_addon_info_fails(
    hass: HomeAssistant, addon_store_info
) -> None:
    """Test setup of a config entry when fetching addon info fails."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})
    addon_store_info.side_effect = HassioAPIError("Boom")

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ),
        patch(
            "homeassistant.components.onboarding.async_is_onboarded", return_value=False
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_addon_not_running(
    hass: HomeAssistant, addon_installed, start_addon
) -> None:
    """Test the addon is started if it is not running."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ),
        patch(
            "homeassistant.components.onboarding.async_is_onboarded", return_value=False
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    start_addon.assert_called_once()


async def test_create_unseated_repair(hass: HomeAssistant) -> None:
    """Test that a repair is created when hardware is inconsistent."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_yellow.get_os_info",
        return_value={"board": "yellow"},
    ), patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=True
    ), patch(
        "homeassistant.components.homeassistant_yellow.check_multi_pan_addon",
        side_effect=HomeAssistantError(),
    ), patch(
        "homeassistant.components.homeassistant_yellow.async_validate_hardware_consistent",
        return_value=False,
    ), patch("homeassistant.components.homeassistant_yellow.ir") as ir:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY

    assert len(ir.async_create_issue.mock_calls) == 1
    assert (
        ir.async_create_issue.mock_calls[0].kwargs["domain"] == "homeassistant_yellow"
    )
    assert ir.async_create_issue.mock_calls[0].kwargs["issue_id"] == "cm4_unseated"


async def test_clear_unseated_repair(hass: HomeAssistant) -> None:
    """Test that a repair is cleared when hardware is consistent."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_yellow.get_os_info",
        return_value={"board": "yellow"},
    ), patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=True
    ), patch(
        "homeassistant.components.homeassistant_yellow.check_multi_pan_addon",
        side_effect=HomeAssistantError(),
    ), patch(
        "homeassistant.components.homeassistant_yellow.async_validate_hardware_consistent",
        return_value=True,
    ), patch("homeassistant.components.homeassistant_yellow.ir") as ir:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY

    assert ir.async_delete_issue.mock_calls == [call(hass, DOMAIN, "cm4_unseated")]
