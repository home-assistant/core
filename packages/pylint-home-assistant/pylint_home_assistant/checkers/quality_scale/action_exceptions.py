"""Checker for ``action-exceptions`` exemptions on controllable platforms.

**Quality-scale-gated** (Silver): only fires for integrations whose
``quality_scale.yaml`` marks ``action-exceptions`` as ``exempt``.

The ``action-exceptions`` rule also covers entity actions, such as turning on
a light or pressing a button, not only integration-registered actions. An
integration with a platform whose entities can be controlled has entity
actions, so the rule cannot be exempt.

https://contributors.home-assistant.io/core/quality-scale/action-exceptions/
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Platform, QualityScaleRule
from pylint_home_assistant.helpers.module_info import get_module_platform
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_exempt

CONTROLLABLE_PLATFORMS: frozenset[str] = frozenset(
    {
        Platform.ALARM_CONTROL_PANEL,
        Platform.BUTTON,
        Platform.CLIMATE,
        Platform.COVER,
        Platform.DATE,
        Platform.DATETIME,
        Platform.FAN,
        Platform.HUMIDIFIER,
        Platform.LAWN_MOWER,
        Platform.LIGHT,
        Platform.LOCK,
        Platform.MEDIA_PLAYER,
        Platform.NOTIFY,
        Platform.NUMBER,
        Platform.REMOTE,
        Platform.SCENE,
        Platform.SELECT,
        Platform.SIREN,
        Platform.SWITCH,
        Platform.TEXT,
        Platform.TIME,
        Platform.VACUUM,
        Platform.VALVE,
        Platform.WATER_HEATER,
    }
)


class ActionExceptionsChecker(BaseChecker):
    """Checker for exempt action-exceptions on controllable platforms."""

    name = "home_assistant_action_exceptions"
    priority = -1
    msgs = {
        "W7464": (
            "Quality scale rule `action-exceptions` is exempt, but the `%s` "
            "platform provides entity actions "
            "(https://contributors.home-assistant.io/core/"
            "quality-scale/action-exceptions/)",
            "home-assistant-action-exceptions-exempt",
            "Used when an integration marks the action-exceptions quality "
            "scale rule as exempt while it has a platform whose entities can "
            "be controlled. Entity actions should raise exceptions on "
            "failure, so the rule applies to them as well.",
        ),
    }
    options = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Check that controllable platforms don't exempt action-exceptions."""
        platform = get_module_platform(node.name)
        if platform not in CONTROLLABLE_PLATFORMS:
            return

        if not quality_scale_rule_is_exempt(node, QualityScaleRule.ACTION_EXCEPTIONS):
            return

        self.add_message(
            "home-assistant-action-exceptions-exempt", node=node, args=(platform,)
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ActionExceptionsChecker(linter))
