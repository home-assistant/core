"""Test deprecated alarm control panel constants."""
from homeassistant.components.alarm_control_panel import const


def import_deprecated_code_format(code_format: const.CodeFormat):
    """Import deprecated code format constant."""
    getattr(const, f"FORMAT_{code_format.name}")


def import_deprecated_entity_feature(
    entity_feature: const.AlarmControlPanelEntityFeature
):
    """Import deprecated entity feature constant."""
    getattr(const, f"SUPPORT_ALARM_{entity_feature.name}")
