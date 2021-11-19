"""Test discovery data templates."""
from zwave_js_server.const import CURRENT_VALUE_PROPERTY, CommandClass
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.zwave_js.discovery_data_template import (
    ConfigurableFanSpeedDataTemplate,
    FixedFanSpeedDataTemplate,
    ZwaveValueID,
)


async def test_fixed_fan_speed_data_template(in_wall_smart_fan_control):
    """Test FixedFanSpeedDataTemplate."""
    data_template = FixedFanSpeedDataTemplate([33, 66, 99])

    values_dict = in_wall_smart_fan_control.get_command_class_values(
        CommandClass.SWITCH_MULTILEVEL
    )
    primary_value = next(
        v
        for v in values_dict.values()
        if isinstance(v, ZwaveValue) and v.property_ == CURRENT_VALUE_PROPERTY
    )

    resolved_data = data_template.resolve_data(primary_value)
    assert data_template.get_speed_config(resolved_data) == [33, 66, 99]


async def test_configurable_fan_speed_data_template(hs_fc200):
    """Test ConfigurableFanSpeedDataTemplate."""
    data_template = ConfigurableFanSpeedDataTemplate(
        configuration_option=ZwaveValueID(5, CommandClass.CONFIGURATION, endpoint=0),
        configuration_value_to_speeds={0: [33, 66, 99], 1: [24, 49, 74, 99]},
    )

    values_dict = hs_fc200.get_command_class_values(CommandClass.SWITCH_MULTILEVEL)
    primary_value = next(
        v
        for v in values_dict.values()
        if isinstance(v, ZwaveValue) and v.property_ == CURRENT_VALUE_PROPERTY
    )

    resolved_data = data_template.resolve_data(primary_value)
    assert data_template.get_speed_config(resolved_data) == [33, 66, 99]
