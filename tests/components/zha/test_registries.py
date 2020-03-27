"""Test ZHA registries."""
from unittest import mock

import pytest

import homeassistant.components.zha.core.registries as registries

MANUFACTURER = "mock manufacturer"
MODEL = "mock model"


@pytest.fixture
def zha_device():
    """Return a mock of ZHA device."""
    dev = mock.MagicMock()
    dev.manufacturer = MANUFACTURER
    dev.model = MODEL
    return dev


@pytest.fixture
def channels(channel):
    """Return a mock of channels."""

    return [channel("level", 8), channel("on_off", 6)]


@pytest.mark.parametrize(
    "rule, matched",
    [
        (registries.MatchRule(), False),
        (registries.MatchRule(channel_names={"level"}), True),
        (registries.MatchRule(channel_names={"level", "no match"}), False),
        (registries.MatchRule(channel_names={"on_off"}), True),
        (registries.MatchRule(channel_names={"on_off", "no match"}), False),
        (registries.MatchRule(channel_names={"on_off", "level"}), True),
        (registries.MatchRule(channel_names={"on_off", "level", "no match"}), False),
        # test generic_id matching
        (registries.MatchRule(generic_ids={"channel_0x0006"}), True),
        (registries.MatchRule(generic_ids={"channel_0x0008"}), True),
        (registries.MatchRule(generic_ids={"channel_0x0006", "channel_0x0008"}), True),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008", "channel_0x0009"}
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
            ),
            True,
        ),
        # manufacturer matching
        (registries.MatchRule(manufacturers="no match"), False),
        (registries.MatchRule(manufacturers=MANUFACTURER), True),
        (
            registries.MatchRule(manufacturers="no match", aux_channels="aux_channel"),
            False,
        ),
        (
            registries.MatchRule(
                manufacturers=MANUFACTURER, aux_channels="aux_channel"
            ),
            True,
        ),
        (registries.MatchRule(models=MODEL), True),
        (registries.MatchRule(models="no match"), False),
        (registries.MatchRule(models=MODEL, aux_channels="aux_channel"), True),
        (registries.MatchRule(models="no match", aux_channels="aux_channel"), False),
        # match everything
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
                manufacturers=MANUFACTURER,
                models=MODEL,
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", manufacturers={"random manuf", MANUFACTURER}
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", manufacturers={"random manuf", "Another manuf"}
            ),
            False,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", manufacturers=lambda x: x == MANUFACTURER
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", manufacturers=lambda x: x != MANUFACTURER
            ),
            False,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", models={"random model", MODEL}
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", models={"random model", "Another model"}
            ),
            False,
        ),
        (
            registries.MatchRule(channel_names="on_off", models=lambda x: x == MODEL),
            True,
        ),
        (
            registries.MatchRule(channel_names="on_off", models=lambda x: x != MODEL),
            False,
        ),
    ],
)
def test_registry_matching(rule, matched, channels):
    """Test strict rule matching."""
    assert rule.strict_matched(MANUFACTURER, MODEL, channels) is matched


@pytest.mark.parametrize(
    "rule, matched",
    [
        (registries.MatchRule(), False),
        (registries.MatchRule(channel_names={"level"}), True),
        (registries.MatchRule(channel_names={"level", "no match"}), False),
        (registries.MatchRule(channel_names={"on_off"}), True),
        (registries.MatchRule(channel_names={"on_off", "no match"}), False),
        (registries.MatchRule(channel_names={"on_off", "level"}), True),
        (registries.MatchRule(channel_names={"on_off", "level", "no match"}), False),
        (
            registries.MatchRule(channel_names={"on_off", "level"}, models="no match"),
            True,
        ),
        (
            registries.MatchRule(
                channel_names={"on_off", "level"},
                models="no match",
                manufacturers="no match",
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names={"on_off", "level"},
                models="no match",
                manufacturers=MANUFACTURER,
            ),
            True,
        ),
        # test generic_id matching
        (registries.MatchRule(generic_ids={"channel_0x0006"}), True),
        (registries.MatchRule(generic_ids={"channel_0x0008"}), True),
        (registries.MatchRule(generic_ids={"channel_0x0006", "channel_0x0008"}), True),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008", "channel_0x0009"}
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008", "channel_0x0009"},
                models="mo match",
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008", "channel_0x0009"},
                models=MODEL,
            ),
            True,
        ),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
            ),
            True,
        ),
        # manufacturer matching
        (registries.MatchRule(manufacturers="no match"), False),
        (registries.MatchRule(manufacturers=MANUFACTURER), True),
        (registries.MatchRule(models=MODEL), True),
        (registries.MatchRule(models="no match"), False),
        # match everything
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
                manufacturers=MANUFACTURER,
                models=MODEL,
            ),
            True,
        ),
    ],
)
def test_registry_loose_matching(rule, matched, channels):
    """Test loose rule matching."""
    assert rule.loose_matched(MANUFACTURER, MODEL, channels) is matched


def test_match_rule_claim_channels_color(channel):
    """Test channel claiming."""
    ch_color = channel("color", 0x300)
    ch_level = channel("level", 8)
    ch_onoff = channel("on_off", 6)

    rule = registries.MatchRule(channel_names="on_off", aux_channels={"color", "level"})
    claimed = rule.claim_channels([ch_color, ch_level, ch_onoff])
    assert {"color", "level", "on_off"} == set([ch.name for ch in claimed])


@pytest.mark.parametrize(
    "rule, match",
    [
        (registries.MatchRule(channel_names={"level"}), {"level"}),
        (registries.MatchRule(channel_names={"level", "no match"}), {"level"}),
        (registries.MatchRule(channel_names={"on_off"}), {"on_off"}),
        (registries.MatchRule(generic_ids="channel_0x0000"), {"basic"}),
        (
            registries.MatchRule(channel_names="level", generic_ids="channel_0x0000"),
            {"basic", "level"},
        ),
        (registries.MatchRule(channel_names={"level", "power"}), {"level", "power"}),
        (
            registries.MatchRule(
                channel_names={"level", "on_off"}, aux_channels={"basic", "power"}
            ),
            {"basic", "level", "on_off", "power"},
        ),
        (registries.MatchRule(channel_names={"color"}), set()),
    ],
)
def test_match_rule_claim_channels(rule, match, channel, channels):
    """Test channel claiming."""
    ch_basic = channel("basic", 0)
    channels.append(ch_basic)
    ch_power = channel("power", 1)
    channels.append(ch_power)

    claimed = rule.claim_channels(channels)
    assert match == set([ch.name for ch in claimed])


@pytest.fixture
def entity_registry():
    """Registry fixture."""
    return registries.ZHAEntityRegistry()


@pytest.mark.parametrize(
    "manufacturer, model, match_name",
    (
        ("random manufacturer", "random model", "OnOff"),
        ("random manufacturer", MODEL, "OnOffModel"),
        (MANUFACTURER, "random model", "OnOffManufacturer"),
        (MANUFACTURER, MODEL, "OnOffModelManufacturer"),
        (MANUFACTURER, "some model", "OnOffMultimodel"),
    ),
)
def test_weighted_match(channel, entity_registry, manufacturer, model, match_name):
    """Test weightedd match."""

    s = mock.sentinel

    @entity_registry.strict_match(
        s.component,
        channel_names="on_off",
        models={MODEL, "another model", "some model"},
    )
    class OnOffMultimodel:
        pass

    @entity_registry.strict_match(s.component, channel_names="on_off")
    class OnOff:
        pass

    @entity_registry.strict_match(
        s.component, channel_names="on_off", manufacturers=MANUFACTURER
    )
    class OnOffManufacturer:
        pass

    @entity_registry.strict_match(s.component, channel_names="on_off", models=MODEL)
    class OnOffModel:
        pass

    @entity_registry.strict_match(
        s.component, channel_names="on_off", models=MODEL, manufacturers=MANUFACTURER
    )
    class OnOffModelManufacturer:
        pass

    ch_on_off = channel("on_off", 6)
    ch_level = channel("level", 8)

    match, claimed = entity_registry.get_entity(
        s.component, manufacturer, model, [ch_on_off, ch_level]
    )

    assert match.__name__ == match_name
    assert claimed == [ch_on_off]
