"""Test the Home Assistant Yellow config flow."""
from unittest.mock import Mock, patch

from homeassistant.components.homeassistant_yellow.const import DOMAIN
from homeassistant.components.zha.core.const import DOMAIN as ZHA_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, MockModule, mock_integration


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
    mock_integration(hass, MockModule("hassio"))

    with patch(
        "homeassistant.components.homeassistant_yellow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant Yellow"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {}
    assert config_entry.title == "Home Assistant Yellow"


async def test_config_flow_single_entry(hass: HomeAssistant) -> None:
    """Test only a single entry is allowed."""
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
        "homeassistant.components.homeassistant_yellow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    mock_setup_entry.assert_not_called()


async def test_option_flow_install_multi_pan_addon(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon."""
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
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "configure_addon"
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    addon_info.return_value["hostname"] = "blah"
    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": "/dev/ttyAMA1",
                "baudrate": 115200,
                "flow_control": True,
            }
        },
    )

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_option_flow_install_multi_pan_addon_zha(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon when a zha config entry exists."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    zha_config_entry = MockConfigEntry(
        data={"device": {"path": "/dev/ttyAMA1"}, "radio_type": "ezsp"},
        domain=ZHA_DOMAIN,
        options={},
        title="Yellow",
    )
    zha_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "configure_addon"
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": "/dev/ttyAMA1",
                "baudrate": 115200,
                "flow_control": True,
            }
        },
    )
    # Check the ZHA migration flow has been started and config entry data is updated
    assert hass.config_entries.options.async_has_matching_flow(
        zha_config_entry.entry_id,
        {"source": "yellow_migration"},
        {
            "name": "Yellow Multi-PAN",
            "new_port": {
                "path": "socket://core-silabs-multiprotocol:9999",
                "baudrate": 115200,
                "flow_control": "hardware",
            },
            "new_radio_type": "efr32",
            "old_port": {
                "path": "/dev/ttyAMA1",
                "baudrate": 115200,
                "flow_control": "hardware",
            },
            "old_radio_type": "efr32",
        },
    )
    zha_option_flows = hass.config_entries.options.async_progress_by_handler(
        zha_config_entry.entry_id
    )
    assert len(zha_option_flows) == 1
    assert zha_option_flows[0]["step_id"] == "finish_yellow_migration"
    assert zha_config_entry.data == {
        "device": {
            "path": "socket://core-silabs-multiprotocol:9999",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
        "radio_type": "ezsp",
    }

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    # Check the ZHA migration flow is not yet finished
    zha_option_flows = hass.config_entries.options.async_progress_by_handler(
        zha_config_entry.entry_id
    )
    assert len(zha_option_flows) == 1
    assert zha_option_flows[0]["step_id"] == "finish_yellow_migration"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Check the ZHA migration flow is finished
    zha_option_flows = hass.config_entries.options.async_progress_by_handler(
        zha_config_entry.entry_id
    )
    assert len(zha_option_flows) == 0


async def test_option_flow_install_multi_pan_addon_zha_other_radio(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon when a zha config entry exists."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    zha_config_entry = MockConfigEntry(
        data={
            "device": {
                "path": "/dev/other_radio",
                "baudrate": 115200,
                "flow_control": "hardware",
            },
            "radio_type": "ezsp",
        },
        domain=ZHA_DOMAIN,
        options={},
        title="Yellow",
    )
    zha_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "configure_addon"
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    addon_info.return_value["hostname"] = "core-silabs-multiprotocol"
    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": "/dev/ttyAMA1",
                "baudrate": 115200,
                "flow_control": True,
            }
        },
    )
    # Check the ZHA migration has already finished
    zha_option_flows = hass.config_entries.options.async_progress_by_handler(
        zha_config_entry.entry_id
    )
    assert len(zha_option_flows) == 0

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Check the ZHA entry data is not changed
    assert zha_config_entry.data == {
        "device": {
            "path": "/dev/other_radio",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
        "radio_type": "ezsp",
    }


async def test_option_flow_non_hassio(
    hass: HomeAssistant,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_hassio"


async def test_option_flow_addon_installed_other_device(
    hass: HomeAssistant,
    addon_store_info,
    addon_installed,
) -> None:
    """Test installing the multi pan addon."""
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
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_installed_other_device"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_option_flow_addon_installed_same_device(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
    addon_installed,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    addon_info.return_value["options"]["device"] = "/dev/ttyAMA1"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "show_revert_guide"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_option_flow_do_not_install_multi_pan_addon(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
) -> None:
    """Test installing the multi pan addon."""
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
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": False,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
