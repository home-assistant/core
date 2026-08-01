"""Checker for missing PARALLEL_UPDATES constant in platform modules.

**Quality-scale-gated** (Silver): only fires for integrations whose
``quality_scale.yaml`` marks ``parallel-updates`` as ``done``.

Every entity platform module must define a ``PARALLEL_UPDATES`` constant that
controls how many entity updates and actions can run concurrently. The
integration author should set this based on the device/API capabilities.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import ENTITY_COMPONENTS, QualityScaleRule
from pylint_home_assistant.helpers.module_info import get_module_platform
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_done


class ParallelUpdatesChecker(BaseChecker):
    """Checker for PARALLEL_UPDATES in platform modules."""

    name = "home_assistant_parallel_updates"
    priority = -1
    msgs = {
        "W7411": (
            "Platform module should define `PARALLEL_UPDATES` constant "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/parallel-updates)",
            "home-assistant-missing-parallel-updates",
            "Used when an entity platform module does not define the "
            "PARALLEL_UPDATES constant. This constant controls how many "
            "entity updates and actions can run concurrently.",
        ),
    }
    options = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Check that platform modules define PARALLEL_UPDATES."""
        # get_module_platform only matches exact platform modules
        # (e.g., sensor.py), not sub-modules (e.g., sensor/storage.py)
        platform = get_module_platform(node.name)
        if platform is None or platform not in ENTITY_COMPONENTS:
            return

        if not quality_scale_rule_is_done(node, QualityScaleRule.PARALLEL_UPDATES):
            return

        for item in node.body:
            if isinstance(item, nodes.Assign) and any(
                isinstance(target, nodes.AssignName)
                and target.name == "PARALLEL_UPDATES"
                for target in item.targets
            ):
                return
            if (
                isinstance(item, nodes.AnnAssign)
                and isinstance(item.target, nodes.AssignName)
                and item.target.name == "PARALLEL_UPDATES"
                and item.value is not None
            ):
                return

        self.add_message("home-assistant-missing-parallel-updates", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ParallelUpdatesChecker(linter))
