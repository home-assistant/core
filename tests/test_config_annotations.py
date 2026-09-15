"""Regression tests: config validators must receive YAML file/line annotations.

The YAML loader annotates every mapping/list node with ``__config_file__`` / ``__line__``
(annotatedyaml ``NodeDictClass`` etc.). A custom trigger/condition/action platform whose
validator reads those annotations (e.g. to point the user at the offending YAML) only works
if the config-validation preprocessing preserves them. These tests use custom platforms as
the annotation consumer and drive them from a real (patched) YAML file.

Cases marked ``xfail`` document where a validator does NOT receive the annotation - either
a config-validation preprocessing strip (trigger ``trigger:`` rename / ``options:`` block)
or the new-style design passing only a synthesized options sub-config (conditions). They
flip to a failure once addressed.
"""

from typing import override
from unittest.mock import Mock, patch

import pytest

from homeassistant.config import (
    YAML_CONFIG_FILE,
    async_hass_config_yaml,
    find_annotation,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.condition import Condition
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .common import MockModule, mock_integration, mock_platform, patch_yaml_files


async def _setup_automation_from_yaml(hass: HomeAssistant, yaml_config: str) -> None:
    """Load an automation from a patched configuration.yaml and set it up."""
    with (
        patch_yaml_files({YAML_CONFIG_FILE: yaml_config}),
        patch("os.path.isfile", return_value=True),
    ):
        config = await async_hass_config_yaml(hass)
        assert await async_setup_component(hass, "automation", config)
        await hass.async_block_till_done()


@pytest.fixture
def trigger_annotations(hass: HomeAssistant) -> list[tuple[str, int | str] | None]:
    """Register a custom trigger platform whose validator records the annotation."""
    seen: list[tuple[str, int | str] | None] = []

    async def async_validate_trigger_config(
        hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        seen.append(find_annotation(config, []))
        return config

    async def async_attach_trigger(
        hass: HomeAssistant,
        config: ConfigType,
        action: TriggerActionType,
        trigger_info: TriggerInfo,
    ) -> CALLBACK_TYPE:
        return lambda: None

    mock_integration(hass, MockModule("test_ann"))
    # spec restricts attributes so the old-style path is taken (no async_get_triggers).
    mock_platform(
        hass,
        "test_ann.trigger",
        Mock(
            spec=["async_validate_trigger_config", "async_attach_trigger"],
            async_validate_trigger_config=async_validate_trigger_config,
            async_attach_trigger=async_attach_trigger,
        ),
    )
    return seen


_TRIGGER_PLATFORM_KEY = """
automation:
  - triggers:
      - platform: test_ann
    actions:
      - event: test_event
"""

_TRIGGER_TRIGGER_KEY = """
automation:
  - triggers:
      - trigger: test_ann
    actions:
      - event: test_event
"""

_TRIGGER_OPTIONS_BLOCK = """
automation:
  - triggers:
      - platform: test_ann
        options:
          foo: bar
    actions:
      - event: test_event
"""


@pytest.mark.parametrize(
    "yaml_config",
    [
        pytest.param(_TRIGGER_PLATFORM_KEY, id="platform_key"),
        pytest.param(
            _TRIGGER_TRIGGER_KEY,
            id="trigger_key",
            marks=pytest.mark.xfail(
                reason=(
                    "config_validation._trigger_pre_validator does dict(value) on the "
                    "trigger:->platform: rename, stripping the annotation"
                ),
                strict=True,
            ),
        ),
        pytest.param(
            _TRIGGER_OPTIONS_BLOCK,
            id="options_block",
            marks=pytest.mark.xfail(
                reason=(
                    "move_options_fields_to_top_level does config.copy() + schema, "
                    "stripping the annotation for new-style option blocks"
                ),
                strict=True,
            ),
        ),
    ],
)
async def test_trigger_validator_receives_annotation(
    hass: HomeAssistant,
    trigger_annotations: list[tuple[str, int | str] | None],
    yaml_config: str,
) -> None:
    """A custom trigger validator must see the YAML file/line of its config."""
    await _setup_automation_from_yaml(hass, yaml_config)
    assert trigger_annotations, "custom trigger validator was not called"
    assert trigger_annotations[-1] is not None


_ACTION_WAIT_FOR_TRIGGER = """
automation:
  - triggers:
      - platform: event
        event_type: test_event
    actions:
      - wait_for_trigger:
          - platform: test_ann
"""


async def test_action_wait_for_trigger_validator_receives_annotation(
    hass: HomeAssistant,
    trigger_annotations: list[tuple[str, int | str] | None],
) -> None:
    """A trigger validator inside a wait_for_trigger action must see the annotation."""
    await _setup_automation_from_yaml(hass, _ACTION_WAIT_FOR_TRIGGER)
    assert trigger_annotations, "custom trigger validator was not called"
    assert trigger_annotations[-1] is not None


@pytest.fixture
def condition_annotations(hass: HomeAssistant) -> list[tuple[str, int | str] | None]:
    """Register a custom condition platform whose validator records the annotation."""
    seen: list[tuple[str, int | str] | None] = []

    class MockCondition(Condition):
        """Condition whose validator records the annotation of its config."""

        @override
        @classmethod
        async def async_validate_config(
            cls, hass: HomeAssistant, config: ConfigType
        ) -> ConfigType:
            seen.append(find_annotation(config, []))
            return config

        @override
        def _async_check(self, **kwargs: object) -> bool:
            return True

    async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
        return {"_": MockCondition}

    mock_integration(hass, MockModule("test_ann_cond"))
    mock_platform(
        hass,
        "test_ann_cond.condition",
        Mock(async_get_conditions=async_get_conditions),
    )
    return seen


_CONDITION_YAML = """
automation:
  - triggers:
      - platform: event
        event_type: test_event
    conditions:
      - condition: test_ann_cond
    actions:
      - event: test_event
"""


@pytest.mark.xfail(
    reason=(
        "new-style conditions run _CONDITION_SCHEMA (strips) and pass a synthesized "
        "options/target sub-config to async_validate_config, so the validator never "
        "receives the annotated full config"
    ),
    strict=True,
)
async def test_condition_validator_receives_annotation(
    hass: HomeAssistant,
    condition_annotations: list[tuple[str, int | str] | None],
) -> None:
    """A custom condition validator must see the YAML file/line of its config."""
    await _setup_automation_from_yaml(hass, _CONDITION_YAML)
    assert condition_annotations, "custom condition validator was not called"
    assert condition_annotations[-1] is not None
