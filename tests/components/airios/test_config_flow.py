"""Test the Airios config flow."""

from unittest.mock import patch

from pyairios import AiriosBoundNodeInfo, AiriosData, AiriosNodeData
from pyairios.constants import BindingStatus, ProductId
from pyairios.registers import Result
from serial.tools import list_ports_common

from homeassistant import config_entries
from homeassistant.components.airios.const import (
    CONF_BRIDGE_RF_ADDRESS,
    CONF_RF_ADDRESS,
    DOMAIN,
    BridgeType,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_config_flow_serial_setup(hass: HomeAssistant) -> None:
    """Test serial RF bridge setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["serial", "network"]

    mockports = []
    mockports.append(list_ports_common.ListPortInfo("/dev/ttyACM9"))
    with patch(
        "serial.tools.list_ports.comports",
        return_value=mockports,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "serial"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"] == {}

    rf_address = 11259375
    with (
        patch(
            "homeassistant.components.airios.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(rf_address, None),
        ) as mock_node_rf_address,
        patch(
            "pyairios.node.AiriosNode.node_product_id",
            return_value=Result(ProductId.BRDG_02R13, None),
        ) as mock_node_product_id,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "/dev/ttyACM9", CONF_SLAVE: 207},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Airios RF bridge ({rf_address:06X})"
    assert result["data"] == {
        CONF_DEVICE: "/dev/ttyACM9",
        CONF_SLAVE: 207,
        CONF_TYPE: BridgeType.SERIAL,
        CONF_BRIDGE_RF_ADDRESS: rf_address,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_node_product_id.mock_calls) == 1
    assert len(mock_node_rf_address.mock_calls) == 1


async def test_config_flow_network_setup(hass: HomeAssistant) -> None:
    """Test network RF bridge setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["serial", "network"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "network"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network"
    assert result["errors"] == {}

    rf_address = 11259375
    with (
        patch(
            "homeassistant.components.airios.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(rf_address, None),
        ) as mock_node_rf_address,
        patch(
            "pyairios.node.AiriosNode.node_product_id",
            return_value=Result(ProductId.BRDG_02R13, None),
        ) as mock_node_product_id,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.2.3.4", CONF_PORT: 502, CONF_SLAVE: 207},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Airios RF bridge ({rf_address:06X})"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 502,
        CONF_SLAVE: 207,
        CONF_TYPE: BridgeType.NETWORK,
        CONF_BRIDGE_RF_ADDRESS: rf_address,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_node_product_id.mock_calls) == 1
    assert len(mock_node_rf_address.mock_calls) == 1


async def test_config_flow_unique_id_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure we can't add the same device twice."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    mockports = []
    mockports.append(list_ports_common.ListPortInfo("/dev/ttyACM9"))
    with patch(
        "serial.tools.list_ports.comports",
        return_value=mockports,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "serial"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.airios.async_setup_entry",
            return_value=True,
        ),
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(0xABCDEF, None),
        ),
        patch(
            "pyairios.node.AiriosNode.node_product_id",
            return_value=Result(ProductId.BRDG_02R13, None),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "/dev/ttyACM9", CONF_SLAVE: 207},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow aborts with unique id mismatch."""

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU

    mockports = []
    mockports.append(list_ports_common.ListPortInfo("/dev/ttyACM9"))
    with patch(
        "serial.tools.list_ports.comports",
        return_value=mockports,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "serial"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.airios.async_setup_entry",
            return_value=True,
        ),
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(0xBAAFEE, None),
        ),
        patch(
            "pyairios.node.AiriosNode.node_product_id",
            return_value=Result(ProductId.BRDG_02R13, None),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "/dev/ttyACM9", CONF_SLAVE: 207},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


async def test_config_flow_unexpected_product_id(hass: HomeAssistant) -> None:
    """Test serial RF bridge setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["serial", "network"]

    mockports = []
    mockports.append(list_ports_common.ListPortInfo("/dev/ttyACM9"))
    with patch(
        "serial.tools.list_ports.comports",
        return_value=mockports,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "serial"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.airios.async_setup_entry",
            return_value=True,
        ),
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(782078, None),
        ),
        patch(
            "pyairios.node.AiriosNode.node_product_id",
            return_value=Result(0x12345678, None),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "/dev/ttyACM9", CONF_SLAVE: 207},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unexpected_product_id"}


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow options."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SCAN_INTERVAL: 25}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_SCAN_INTERVAL: 25}


async def test_subentry_flow_bind_controller(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry flow to bind a controller."""
    with (
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(11259375, None),
        ),
        patch(
            "pyairios.Airios.nodes",
            return_value=[],
        ),
        patch(
            "pyairios.Airios.fetch",
            return_value=AiriosData(
                bridge_rf_address=123456,
                nodes={
                    123123: AiriosNodeData(
                        slave_id=2,
                        rf_address=Result(123123, None),
                        product_id=Result(ProductId.VMD_02RPS78, None),
                        product_name=None,
                        sw_version=None,
                        rf_comm_status=None,
                        battery_status=None,
                        fault_status=None,
                    )
                },
            ),
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "controller"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(11259375, None),
        ),
        patch(
            "pyairios.Airios.nodes",
            return_value=[],
        ),
        patch("pyairios.Airios.bind_controller", return_value=True),
        patch(
            "pyairios.Airios.bind_status",
            return_value=BindingStatus.OUTGOING_BINDING_COMPLETED,
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "My controller",
                CONF_RF_ADDRESS: 123456,
                CONF_DEVICE: "Siber DF Optima 2",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "do_bind_controller"

    with (
        patch(
            "pyairios.brdg_02r13.BRDG02R13.nodes",
            return_value=[AiriosBoundNodeInfo(2, ProductId.VMD_02RPS78, 123456)],
        ),
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(123456, None),
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: "My controller",
        CONF_SLAVE: 2,
        CONF_DEVICE: ProductId.VMD_02RPS78,
        CONF_RF_ADDRESS: 123456,
    }


async def test_subentry_flow_bind_accessory(
    hass: HomeAssistant,
    mock_config_entry_ctrl: MockConfigEntry,
) -> None:
    """Test subentry flow to bind an accessory."""
    with (
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(11259375, None),
        ),
        patch(
            "pyairios.Airios.nodes",
            return_value=[],
        ),
        patch(
            "pyairios.Airios.fetch",
            return_value=AiriosData(
                bridge_rf_address=123456,
                nodes={
                    123123: AiriosNodeData(
                        slave_id=2,
                        rf_address=Result(123123, None),
                        product_id=Result(ProductId.VMD_02RPS78, None),
                        product_name=None,
                        sw_version=None,
                        rf_comm_status=None,
                        battery_status=None,
                        fault_status=None,
                    )
                },
            ),
        ),
    ):
        mock_config_entry_ctrl.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_ctrl.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    with patch(
        "pyairios.Airios.nodes",
        return_value=[
            AiriosBoundNodeInfo(
                slave_id=2, product_id=ProductId.VMD_02RPS78, rf_address=123123
            )
        ],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry_ctrl.entry_id, "accessory"),
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(11259375, None),
        ),
        patch(
            "pyairios.Airios.nodes",
            return_value=[
                AiriosBoundNodeInfo(
                    slave_id=2, product_id=ProductId.VMD_02RPS78, rf_address=123123
                )
            ],
        ),
        patch("pyairios.Airios.bind_accessory", return_value=True),
        patch(
            "pyairios.Airios.bind_status",
            return_value=BindingStatus.INCOMING_BINDING_COMPLETED,
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "My accessory",
                CONF_SLAVE: 2,
                CONF_DEVICE: "Siber 4 button remote",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "do_bind_accessory"

    with (
        patch(
            "pyairios.brdg_02r13.BRDG02R13.nodes",
            return_value=[
                AiriosBoundNodeInfo(
                    slave_id=2, product_id=ProductId.VMD_02RPS78, rf_address=123123
                ),
                AiriosBoundNodeInfo(
                    slave_id=3, product_id=ProductId.VMN_05LM02, rf_address=123456
                ),
            ],
        ),
        patch(
            "pyairios.node.AiriosNode.node_rf_address",
            return_value=Result(123456, None),
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: "My accessory",
        CONF_SLAVE: 3,
        CONF_DEVICE: ProductId.VMN_05LM02,
        CONF_RF_ADDRESS: 123456,
    }
