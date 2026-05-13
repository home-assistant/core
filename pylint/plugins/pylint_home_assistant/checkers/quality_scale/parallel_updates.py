"""Checker for missing PARALLEL_UPDATES constant in platform modules.

**Quality-scale-gated** (Silver): only fires for integrations whose
``quality_scale.yaml`` marks ``parallel-updates`` as ``done``.

Every entity platform module must define a ``PARALLEL_UPDATES`` constant that
controls how many updates can run concurrently. The integration author should
set this based on the device/API capabilities.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import ENTITY_COMPONENTS, QualityScaleRule
from pylint_home_assistant.helpers.module_info import parse_module
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_done


class ParallelUpdatesChecker(BaseChecker):
    """Checker for PARALLEL_UPDATES in platform modules."""

    name = "home_assistant_parallel_updates"
    priority = -1
    msgs = {
        "W7409": (
            "Platform module should define `PARALLEL_UPDATES` constant "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/parallel-updates)",
            "home-assistant-missing-parallel-updates",
            "Used when an entity platform module does not define the "
            "PARALLEL_UPDATES constant. This constant controls how many "
            "entity updates can run concurrently.",
        ),
    }
    options = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Check that platform modules define PARALLEL_UPDATES."""
        parsed = parse_module(node.name)
        if parsed is None or parsed.module not in ENTITY_COMPONENTS:
            return

        if not quality_scale_rule_is_done(node, QualityScaleRule.PARALLEL_UPDATES):
            return

        for item in node.body:
            if (
                isinstance(item, nodes.Assign)
                and isinstance(item.targets[0], nodes.AssignName)
                and item.targets[0].name == "PARALLEL_UPDATES"
            ):
                return

        self.add_message("home-assistant-missing-parallel-updates", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ParallelUpdatesChecker(linter))
