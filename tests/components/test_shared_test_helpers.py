"""Tests for the shared trigger/condition target-support test helpers.

`assert_triggers_target_support` and `assert_conditions_target_support` (in
`tests.components.common`) let each modern trigger/condition test module certify,
against its own registry, that every trigger it tests either supports a user
target via the shared machinery (``STANDARD``), exposes no target
(``NONE``), or resolves a target with its own machinery (``CUSTOM``). The
per-domain axis reduction relies on that certification, so these tests pin that
the helpers actually reject the violations they are meant to catch, using
synthetic classes that each introduce exactly one defect.
"""

from typing import Any, cast

import pytest
import voluptuous as vol

from homeassistant.const import CONF_TARGET, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import (
    Condition,
    ConditionConfig,
    make_entity_state_condition,
)
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerConfig,
    make_entity_target_state_trigger,
)

from .common import (
    TargetSupport,
    assert_conditions_target_support,
    assert_triggers_target_support,
)

# Valid baselines created by the public factories: proper entity-base classes that
# inherit the target machinery unmodified and carry the standard target slot.
_ValidTrigger = make_entity_target_state_trigger("test", STATE_ON)
_ValidCondition = make_entity_state_condition("test", STATE_ON)

# A schema without a ``target`` marker (a class that does not expose a user target).
_NO_TARGET_SCHEMA = vol.Schema({vol.Optional("options"): dict})
# A schema that does expose the standard user target slot.
_TARGET_SCHEMA = vol.Schema({vol.Required(CONF_TARGET): cv.TARGET_FIELDS})


class _MachineryOverrideTrigger(_ValidTrigger):
    """Overrides target-resolution machinery (``count_matches``)."""

    def count_matches(self, *args: Any, **kwargs: Any) -> Any:
        """Trip the machinery-override check."""
        raise NotImplementedError


class _NoTargetSlotTrigger(_ValidTrigger):
    """Entity-base class whose schema drops the standard ``target`` slot."""

    _schema = _NO_TARGET_SCHEMA


class _MutatesConfigTargetTrigger(_ValidTrigger):
    """``__init__`` rewrites the user target before delegating."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Rewrite the user target."""
        config.target = {CONF_TARGET: {}}
        super().__init__(hass, config)


class _InitNoSuperTrigger(_ValidTrigger):
    """``__init__`` does not delegate the config to super."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Fail to delegate to super."""
        # pylint: disable=super-init-not-called,unused-argument
        self._hass = hass


class _RebuildsConfigTrigger(_ValidTrigger):
    """``__init__`` rebuilds the config object."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Rebuild the config."""
        config = TriggerConfig(target=config.target)
        super().__init__(hass, config)


class _AssignsTargetTrigger(_ValidTrigger):
    """``__init__`` assigns ``self._target``."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Assign the resolved target directly."""
        super().__init__(hass, config)
        self._target = config.target


class _WideningEntityFilterTrigger(_ValidTrigger):
    """``entity_filter`` override that does not narrow the base result."""

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Return the input unchanged instead of narrowing it."""
        return entities


class _CustomTargetTrigger(Trigger):
    """Not an entity-base class; exposes a target slot but resolves it itself."""

    _schema = _TARGET_SCHEMA


class _NestedBadInitTrigger(_MutatesConfigTargetTrigger):
    """Clean delegating ``__init__`` above a parent that rewrites the target.

    The child initializer is hygienic on its own; the defect lives on the
    parent, so this only fails if the MRO scan continues past the clean child.
    """

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        # pylint: disable=useless-parent-delegation
        """Delegate cleanly to super."""
        super().__init__(hass, config)


class _NestedWideningEntityFilterTrigger(_WideningEntityFilterTrigger):
    """Narrowing ``entity_filter`` above a parent that widens the base result.

    The child override narrows correctly; the defect lives on the parent, so
    this only fails if the MRO scan continues past the clean child.
    """

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Narrow the base result."""
        return super().entity_filter(entities) & entities


class _MachineryOverrideCondition(_ValidCondition):
    """Overrides target-resolution machinery (``_async_check``)."""

    async def _async_check(self, *args: Any, **kwargs: Any) -> Any:
        """Trip the machinery-override check."""
        raise NotImplementedError


class _NoTargetSlotCondition(_ValidCondition):
    """Entity-base class whose schema drops the standard ``target`` slot."""

    _schema = _NO_TARGET_SCHEMA


class _MutatesConfigTargetCondition(_ValidCondition):
    """``__init__`` rewrites the user target.

    ``ConditionConfig`` is not frozen, so this would rewrite the target at
    runtime; the helper must catch it statically.
    """

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Rewrite the user target."""
        config.target = {CONF_TARGET: {}}
        super().__init__(hass, config)


class _RebuildsConfigCondition(_ValidCondition):
    """``__init__`` rebuilds the config object (exercises the ConditionConfig wiring)."""

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Rebuild the config."""
        config = ConditionConfig(target=config.target)
        super().__init__(hass, config)


class _CustomTargetCondition(Condition):
    """Not an entity-base class; exposes a target slot but resolves it itself."""

    _schema = _TARGET_SCHEMA


class _NestedBadInitCondition(_MutatesConfigTargetCondition):
    """Clean delegating ``__init__`` above a parent that rewrites the target.

    Mirrors ``_NestedBadInitTrigger`` on the condition side, where
    ``_init_hygiene_violation`` is wired with ``config_cls="ConditionConfig"``.
    """

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        # pylint: disable=useless-parent-delegation
        """Delegate cleanly to super."""
        super().__init__(hass, config)


@pytest.mark.parametrize(
    ("registry", "declaration", "match"),
    [
        pytest.param(
            {"x": _MachineryOverrideTrigger},
            {"x": TargetSupport.STANDARD},
            "overrides target machinery",
            id="standard-overrides-machinery",
        ),
        pytest.param(
            {"x": _NoTargetSlotTrigger},
            {"x": TargetSupport.STANDARD},
            "does not carry the standard",
            id="standard-missing-target-slot",
        ),
        pytest.param(
            {"x": _MutatesConfigTargetTrigger},
            {"x": TargetSupport.STANDARD},
            "must not assign to config.target",
            id="standard-mutates-config-target",
        ),
        pytest.param(
            {"x": _NestedBadInitTrigger},
            {"x": TargetSupport.STANDARD},
            "must not assign to config.target",
            id="standard-nested-bad-init",
        ),
        pytest.param(
            {"x": _InitNoSuperTrigger},
            {"x": TargetSupport.STANDARD},
            "must delegate the unmodified config",
            id="standard-init-no-super",
        ),
        pytest.param(
            {"x": _RebuildsConfigTrigger},
            {"x": TargetSupport.STANDARD},
            "must not rebuild the config object",
            id="standard-rebuilds-config",
        ),
        pytest.param(
            {"x": _AssignsTargetTrigger},
            {"x": TargetSupport.STANDARD},
            "must not assign self._target",
            id="standard-assigns-target",
        ),
        pytest.param(
            {"x": _WideningEntityFilterTrigger},
            {"x": TargetSupport.STANDARD},
            "entity_filter override must narrow",
            id="standard-widens-entity-filter",
        ),
        pytest.param(
            {"x": _NestedWideningEntityFilterTrigger},
            {"x": TargetSupport.STANDARD},
            "entity_filter override must narrow",
            id="standard-nested-widening-filter",
        ),
        pytest.param(
            {"x": _CustomTargetTrigger},
            {"x": TargetSupport.STANDARD},
            "does not subclass",
            id="standard-not-entity-base",
        ),
        pytest.param(
            {"x": _ValidTrigger},
            {"x": TargetSupport.NONE},
            "declared TargetSupport.NONE",
            id="none-exposes-target-slot",
        ),
        pytest.param(
            {"x": _NoTargetSlotTrigger},
            {"x": TargetSupport.CUSTOM},
            "declared TargetSupport.CUSTOM",
            id="custom-missing-target-slot",
        ),
        pytest.param(
            {"x": _ValidTrigger, "y": _ValidTrigger},
            {"x": TargetSupport.STANDARD},
            "registered but not declared",
            id="registry-key-undeclared",
        ),
        pytest.param(
            {"x": _ValidTrigger},
            {"x": TargetSupport.STANDARD, "y": TargetSupport.STANDARD},
            "declared but not registered",
            id="declared-key-unregistered",
        ),
        pytest.param(
            {"x": _ValidTrigger},
            {"x": cast(TargetSupport, "standard")},
            "invalid target-support declaration value",
            id="raw-string-not-enum-member",
        ),
    ],
)
def test_assert_triggers_target_support_rejects(
    registry: dict[str, type[Trigger]],
    declaration: dict[str, TargetSupport],
    match: str,
) -> None:
    """Each synthetic defect is rejected by the trigger helper."""
    with pytest.raises(AssertionError, match=match):
        assert_triggers_target_support(registry, declaration)


@pytest.mark.parametrize(
    ("registry", "declaration", "match"),
    [
        pytest.param(
            {"x": _MachineryOverrideCondition},
            {"x": TargetSupport.STANDARD},
            "overrides target machinery",
            id="standard-overrides-machinery",
        ),
        pytest.param(
            {"x": _NoTargetSlotCondition},
            {"x": TargetSupport.STANDARD},
            "does not carry the standard",
            id="standard-missing-target-slot",
        ),
        pytest.param(
            {"x": _MutatesConfigTargetCondition},
            {"x": TargetSupport.STANDARD},
            "must not assign to config.target",
            id="standard-mutates-config-target",
        ),
        pytest.param(
            {"x": _NestedBadInitCondition},
            {"x": TargetSupport.STANDARD},
            "must not assign to config.target",
            id="standard-nested-bad-init",
        ),
        pytest.param(
            {"x": _RebuildsConfigCondition},
            {"x": TargetSupport.STANDARD},
            "must not rebuild the config object",
            id="standard-rebuilds-config",
        ),
        pytest.param(
            {"x": _CustomTargetCondition},
            {"x": TargetSupport.STANDARD},
            "does not subclass",
            id="standard-not-entity-base",
        ),
        pytest.param(
            {"x": _ValidCondition},
            {"x": TargetSupport.NONE},
            "declared TargetSupport.NONE",
            id="none-exposes-target-slot",
        ),
        pytest.param(
            {"x": _NoTargetSlotCondition},
            {"x": TargetSupport.CUSTOM},
            "declared TargetSupport.CUSTOM",
            id="custom-missing-target-slot",
        ),
        pytest.param(
            {"x": _ValidCondition, "y": _ValidCondition},
            {"x": TargetSupport.STANDARD},
            "registered but not declared",
            id="registry-key-undeclared",
        ),
        pytest.param(
            {"x": _ValidCondition},
            {"x": TargetSupport.STANDARD, "y": TargetSupport.STANDARD},
            "declared but not registered",
            id="declared-key-unregistered",
        ),
        pytest.param(
            {"x": _ValidCondition},
            {"x": cast(TargetSupport, "standard")},
            "invalid target-support declaration value",
            id="raw-string-not-enum-member",
        ),
    ],
)
def test_assert_conditions_target_support_rejects(
    registry: dict[str, type[Condition]],
    declaration: dict[str, TargetSupport],
    match: str,
) -> None:
    """Each synthetic defect is rejected by the condition helper."""
    with pytest.raises(AssertionError, match=match):
        assert_conditions_target_support(registry, declaration)


def test_assert_triggers_target_support_accepts_valid_declaration() -> None:
    """A registry matching a correct declaration passes for all three states."""
    assert_triggers_target_support(
        {
            "standard": _ValidTrigger,
            "none": _NoTargetSlotTrigger,
            "custom": _CustomTargetTrigger,
        },
        {
            "standard": TargetSupport.STANDARD,
            "none": TargetSupport.NONE,
            "custom": TargetSupport.CUSTOM,
        },
    )


def test_assert_conditions_target_support_accepts_valid_declaration() -> None:
    """A registry matching a correct declaration passes for all three states."""
    assert_conditions_target_support(
        {
            "standard": _ValidCondition,
            "none": _NoTargetSlotCondition,
            "custom": _CustomTargetCondition,
        },
        {
            "standard": TargetSupport.STANDARD,
            "none": TargetSupport.NONE,
            "custom": TargetSupport.CUSTOM,
        },
    )
