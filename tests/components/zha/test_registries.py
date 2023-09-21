"""Test ZHA registries."""
from __future__ import annotations

import importlib
import inspect
import typing
from unittest import mock

import pytest
import zhaquirks

from homeassistant.components.zha.binary_sensor import IASZone
import homeassistant.components.zha.core.registries as registries
from homeassistant.helpers import entity_registry as er

if typing.TYPE_CHECKING:
    from homeassistant.components.zha.core.entity import ZhaEntity

MANUFACTURER = "mock manufacturer"
MODEL = "mock model"
QUIRK_CLASS = "mock.test.quirk.class"
QUIRK_CLASS_SHORT = "quirk.class"


@pytest.fixture
def zha_device():
    """Return a mock of ZHA device."""
    dev = mock.MagicMock()
    dev.manufacturer = MANUFACTURER
    dev.model = MODEL
    dev.quirk_class = QUIRK_CLASS
    return dev


@pytest.fixture
def cluster_handlers(cluster_handler):
    """Return a mock of cluster_handlers."""

    return [cluster_handler("level", 8), cluster_handler("on_off", 6)]


@pytest.mark.parametrize(
    ("rule", "matched"),
    [
        (registries.MatchRule(), False),
        (registries.MatchRule(cluster_handler_names={"level"}), True),
        (registries.MatchRule(cluster_handler_names={"level", "no match"}), False),
        (registries.MatchRule(cluster_handler_names={"on_off"}), True),
        (registries.MatchRule(cluster_handler_names={"on_off", "no match"}), False),
        (registries.MatchRule(cluster_handler_names={"on_off", "level"}), True),
        (
            registries.MatchRule(cluster_handler_names={"on_off", "level", "no match"}),
            False,
        ),
        # test generic_id matching
        (registries.MatchRule(generic_ids={"cluster_handler_0x0006"}), True),
        (registries.MatchRule(generic_ids={"cluster_handler_0x0008"}), True),
        (
            registries.MatchRule(
                generic_ids={"cluster_handler_0x0006", "cluster_handler_0x0008"}
            ),
            True,
        ),
        (
            registries.MatchRule(
                generic_ids={
                    "cluster_handler_0x0006",
                    "cluster_handler_0x0008",
                    "cluster_handler_0x0009",
                }
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={"cluster_handler_0x0006", "cluster_handler_0x0008"},
                cluster_handler_names={"on_off", "level"},
            ),
            True,
        ),
        # manufacturer matching
        (registries.MatchRule(manufacturers="no match"), False),
        (registries.MatchRule(manufacturers=MANUFACTURER), True),
        (
            registries.MatchRule(
                manufacturers="no match", aux_cluster_handlers="aux_cluster_handler"
            ),
            False,
        ),
        (
            registries.MatchRule(
                manufacturers=MANUFACTURER, aux_cluster_handlers="aux_cluster_handler"
            ),
            True,
        ),
        (registries.MatchRule(models=MODEL), True),
        (registries.MatchRule(models="no match"), False),
        (
            registries.MatchRule(
                models=MODEL, aux_cluster_handlers="aux_cluster_handler"
            ),
            True,
        ),
        (
            registries.MatchRule(
                models="no match", aux_cluster_handlers="aux_cluster_handler"
            ),
            False,
        ),
        (registries.MatchRule(quirk_classes=QUIRK_CLASS), True),
        (registries.MatchRule(quirk_classes="no match"), False),
        (
            registries.MatchRule(
                quirk_classes=QUIRK_CLASS, aux_cluster_handlers="aux_cluster_handler"
            ),
            True,
        ),
        (
            registries.MatchRule(
                quirk_classes="no match", aux_cluster_handlers="aux_cluster_handler"
            ),
            False,
        ),
        # match everything
        (
            registries.MatchRule(
                generic_ids={"cluster_handler_0x0006", "cluster_handler_0x0008"},
                cluster_handler_names={"on_off", "level"},
                manufacturers=MANUFACTURER,
                models=MODEL,
                quirk_classes=QUIRK_CLASS,
            ),
            True,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off",
                manufacturers={"random manuf", MANUFACTURER},
            ),
            True,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off",
                manufacturers={"random manuf", "Another manuf"},
            ),
            False,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off",
                manufacturers=lambda x: x == MANUFACTURER,
            ),
            True,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off",
                manufacturers=lambda x: x != MANUFACTURER,
            ),
            False,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off", models={"random model", MODEL}
            ),
            True,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off", models={"random model", "Another model"}
            ),
            False,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off", models=lambda x: x == MODEL
            ),
            True,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off", models=lambda x: x != MODEL
            ),
            False,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off",
                quirk_classes={"random quirk", QUIRK_CLASS},
            ),
            True,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off",
                quirk_classes={"random quirk", "another quirk"},
            ),
            False,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off", quirk_classes=lambda x: x == QUIRK_CLASS
            ),
            True,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off", quirk_classes=lambda x: x != QUIRK_CLASS
            ),
            False,
        ),
        (
            registries.MatchRule(
                cluster_handler_names="on_off", quirk_classes=QUIRK_CLASS_SHORT
            ),
            True,
        ),
    ],
)
def test_registry_matching(rule, matched, cluster_handlers) -> None:
    """Test strict rule matching."""
    assert (
        rule.strict_matched(MANUFACTURER, MODEL, cluster_handlers, QUIRK_CLASS)
        is matched
    )


@pytest.mark.parametrize(
    ("rule", "matched"),
    [
        (registries.MatchRule(), False),
        (registries.MatchRule(cluster_handler_names={"level"}), True),
        (registries.MatchRule(cluster_handler_names={"level", "no match"}), False),
        (registries.MatchRule(cluster_handler_names={"on_off"}), True),
        (registries.MatchRule(cluster_handler_names={"on_off", "no match"}), False),
        (registries.MatchRule(cluster_handler_names={"on_off", "level"}), True),
        (
            registries.MatchRule(cluster_handler_names={"on_off", "level", "no match"}),
            False,
        ),
        (
            registries.MatchRule(
                cluster_handler_names={"on_off", "level"}, models="no match"
            ),
            True,
        ),
        (
            registries.MatchRule(
                cluster_handler_names={"on_off", "level"},
                models="no match",
                manufacturers="no match",
            ),
            True,
        ),
        (
            registries.MatchRule(
                cluster_handler_names={"on_off", "level"},
                models="no match",
                manufacturers=MANUFACTURER,
            ),
            True,
        ),
        # test generic_id matching
        (registries.MatchRule(generic_ids={"cluster_handler_0x0006"}), True),
        (registries.MatchRule(generic_ids={"cluster_handler_0x0008"}), True),
        (
            registries.MatchRule(
                generic_ids={"cluster_handler_0x0006", "cluster_handler_0x0008"}
            ),
            True,
        ),
        (
            registries.MatchRule(
                generic_ids={
                    "cluster_handler_0x0006",
                    "cluster_handler_0x0008",
                    "cluster_handler_0x0009",
                }
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={
                    "cluster_handler_0x0006",
                    "cluster_handler_0x0008",
                    "cluster_handler_0x0009",
                },
                models="mo match",
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={
                    "cluster_handler_0x0006",
                    "cluster_handler_0x0008",
                    "cluster_handler_0x0009",
                },
                models=MODEL,
            ),
            True,
        ),
        (
            registries.MatchRule(
                generic_ids={"cluster_handler_0x0006", "cluster_handler_0x0008"},
                cluster_handler_names={"on_off", "level"},
            ),
            True,
        ),
        # manufacturer matching
        (registries.MatchRule(manufacturers="no match"), False),
        (registries.MatchRule(manufacturers=MANUFACTURER), True),
        (registries.MatchRule(models=MODEL), True),
        (registries.MatchRule(models="no match"), False),
        (registries.MatchRule(quirk_classes=QUIRK_CLASS), True),
        (registries.MatchRule(quirk_classes="no match"), False),
        # match everything
        (
            registries.MatchRule(
                generic_ids={"cluster_handler_0x0006", "cluster_handler_0x0008"},
                cluster_handler_names={"on_off", "level"},
                manufacturers=MANUFACTURER,
                models=MODEL,
                quirk_classes=QUIRK_CLASS,
            ),
            True,
        ),
    ],
)
def test_registry_loose_matching(rule, matched, cluster_handlers) -> None:
    """Test loose rule matching."""
    assert (
        rule.loose_matched(MANUFACTURER, MODEL, cluster_handlers, QUIRK_CLASS)
        is matched
    )


def test_match_rule_claim_cluster_handlers_color(cluster_handler) -> None:
    """Test cluster handler claiming."""
    ch_color = cluster_handler("color", 0x300)
    ch_level = cluster_handler("level", 8)
    ch_onoff = cluster_handler("on_off", 6)

    rule = registries.MatchRule(
        cluster_handler_names="on_off", aux_cluster_handlers={"color", "level"}
    )
    claimed = rule.claim_cluster_handlers([ch_color, ch_level, ch_onoff])
    assert {"color", "level", "on_off"} == {ch.name for ch in claimed}


@pytest.mark.parametrize(
    ("rule", "match"),
    [
        (registries.MatchRule(cluster_handler_names={"level"}), {"level"}),
        (registries.MatchRule(cluster_handler_names={"level", "no match"}), {"level"}),
        (registries.MatchRule(cluster_handler_names={"on_off"}), {"on_off"}),
        (registries.MatchRule(generic_ids="cluster_handler_0x0000"), {"basic"}),
        (
            registries.MatchRule(
                cluster_handler_names="level", generic_ids="cluster_handler_0x0000"
            ),
            {"basic", "level"},
        ),
        (
            registries.MatchRule(cluster_handler_names={"level", "power"}),
            {"level", "power"},
        ),
        (
            registries.MatchRule(
                cluster_handler_names={"level", "on_off"},
                aux_cluster_handlers={"basic", "power"},
            ),
            {"basic", "level", "on_off", "power"},
        ),
        (registries.MatchRule(cluster_handler_names={"color"}), set()),
    ],
)
def test_match_rule_claim_cluster_handlers(
    rule, match, cluster_handler, cluster_handlers
) -> None:
    """Test cluster handler claiming."""
    ch_basic = cluster_handler("basic", 0)
    cluster_handlers.append(ch_basic)
    ch_power = cluster_handler("power", 1)
    cluster_handlers.append(ch_power)

    claimed = rule.claim_cluster_handlers(cluster_handlers)
    assert match == {ch.name for ch in claimed}


@pytest.fixture
def entity_registry():
    """Registry fixture."""
    return registries.ZHAEntityRegistry()


@pytest.mark.parametrize(
    ("manufacturer", "model", "quirk_class", "match_name"),
    (
        ("random manufacturer", "random model", "random.class", "OnOff"),
        ("random manufacturer", MODEL, "random.class", "OnOffModel"),
        (MANUFACTURER, "random model", "random.class", "OnOffManufacturer"),
        ("random manufacturer", "random model", QUIRK_CLASS, "OnOffQuirk"),
        (MANUFACTURER, MODEL, "random.class", "OnOffModelManufacturer"),
        (MANUFACTURER, "some model", "random.class", "OnOffMultimodel"),
    ),
)
def test_weighted_match(
    cluster_handler,
    entity_registry: er.EntityRegistry,
    manufacturer,
    model,
    quirk_class,
    match_name,
) -> None:
    """Test weightedd match."""

    s = mock.sentinel

    @entity_registry.strict_match(
        s.component,
        cluster_handler_names="on_off",
        models={MODEL, "another model", "some model"},
    )
    class OnOffMultimodel:
        pass

    @entity_registry.strict_match(s.component, cluster_handler_names="on_off")
    class OnOff:
        pass

    @entity_registry.strict_match(
        s.component, cluster_handler_names="on_off", manufacturers=MANUFACTURER
    )
    class OnOffManufacturer:
        pass

    @entity_registry.strict_match(
        s.component, cluster_handler_names="on_off", models=MODEL
    )
    class OnOffModel:
        pass

    @entity_registry.strict_match(
        s.component,
        cluster_handler_names="on_off",
        models=MODEL,
        manufacturers=MANUFACTURER,
    )
    class OnOffModelManufacturer:
        pass

    @entity_registry.strict_match(
        s.component, cluster_handler_names="on_off", quirk_classes=QUIRK_CLASS
    )
    class OnOffQuirk:
        pass

    ch_on_off = cluster_handler("on_off", 6)
    ch_level = cluster_handler("level", 8)

    match, claimed = entity_registry.get_entity(
        s.component, manufacturer, model, [ch_on_off, ch_level], quirk_class
    )

    assert match.__name__ == match_name
    assert claimed == [ch_on_off]


def test_multi_sensor_match(
    cluster_handler, entity_registry: er.EntityRegistry
) -> None:
    """Test multi-entity match."""

    s = mock.sentinel

    @entity_registry.multipass_match(
        s.binary_sensor,
        cluster_handler_names="smartenergy_metering",
    )
    class SmartEnergySensor2:
        pass

    ch_se = cluster_handler("smartenergy_metering", 0x0702)
    ch_illuminati = cluster_handler("illuminance", 0x0401)

    match, claimed = entity_registry.get_multi_entity(
        "manufacturer",
        "model",
        cluster_handlers=[ch_se, ch_illuminati],
        quirk_class="quirk_class",
    )

    assert s.binary_sensor in match
    assert s.component not in match
    assert set(claimed) == {ch_se}
    assert {cls.entity_class.__name__ for cls in match[s.binary_sensor]} == {
        SmartEnergySensor2.__name__
    }

    @entity_registry.multipass_match(
        s.component,
        cluster_handler_names="smartenergy_metering",
        aux_cluster_handlers="illuminance",
    )
    class SmartEnergySensor1:
        pass

    @entity_registry.multipass_match(
        s.binary_sensor,
        cluster_handler_names="smartenergy_metering",
        aux_cluster_handlers="illuminance",
    )
    class SmartEnergySensor3:
        pass

    match, claimed = entity_registry.get_multi_entity(
        "manufacturer",
        "model",
        cluster_handlers={ch_se, ch_illuminati},
        quirk_class="quirk_class",
    )

    assert s.binary_sensor in match
    assert s.component in match
    assert set(claimed) == {ch_se, ch_illuminati}
    assert {cls.entity_class.__name__ for cls in match[s.binary_sensor]} == {
        SmartEnergySensor2.__name__,
        SmartEnergySensor3.__name__,
    }
    assert {cls.entity_class.__name__ for cls in match[s.component]} == {
        SmartEnergySensor1.__name__
    }


def iter_all_rules() -> typing.Iterable[registries.MatchRule, list[type[ZhaEntity]]]:
    """Iterate over all match rules and their corresponding entities."""

    for rules in registries.ZHA_ENTITIES._strict_registry.values():
        for rule, entity in rules.items():
            yield rule, [entity]

    for rules in registries.ZHA_ENTITIES._multi_entity_registry.values():
        for multi in rules.values():
            for rule, entities in multi.items():
                yield rule, entities

    for rules in registries.ZHA_ENTITIES._config_diagnostic_entity_registry.values():
        for multi in rules.values():
            for rule, entities in multi.items():
                yield rule, entities


def test_quirk_classes() -> None:
    """Make sure that quirk_classes in components matches are valid."""

    def find_quirk_class(base_obj, quirk_mod, quirk_cls):
        """Find a specific quirk class."""

        module = importlib.import_module(quirk_mod)
        clss = dict(inspect.getmembers(module, inspect.isclass))
        # Check quirk_cls in module classes
        return quirk_cls in clss

    def quirk_class_validator(value):
        """Validate quirk classes during self test."""
        if callable(value):
            # Callables cannot be tested
            return

        if isinstance(value, (frozenset, set, list)):
            for v in value:
                # Unpack the value if needed
                quirk_class_validator(v)
            return

        quirk_tok = value.rsplit(".", 1)
        if len(quirk_tok) != 2:
            # quirk_class is at least __module__.__class__
            raise ValueError(f"Invalid quirk class : '{value}'")

        if not find_quirk_class(zhaquirks, quirk_tok[0], quirk_tok[1]):
            raise ValueError(f"Quirk class '{value}' does not exists.")

    for rule, _ in iter_all_rules():
        quirk_class_validator(rule.quirk_classes)


def test_entity_names() -> None:
    """Make sure that all handlers expose entities with valid names."""

    for _, entities in iter_all_rules():
        for entity in entities:
            if hasattr(entity, "_attr_name"):
                # The entity has a name
                assert isinstance(entity._attr_name, str) and entity._attr_name
            else:
                # The only exception (for now) is IASZone
                assert entity is IASZone
