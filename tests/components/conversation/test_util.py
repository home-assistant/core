"""Test the conversation utils."""

from homeassistant.components.conversation.util import create_matcher


def test_create_matcher() -> None:
    """Test the create matcher method."""
    # Basic sentence
    pattern = create_matcher("Hello world")
    assert pattern.match("Hello world") is not None

    # Match a part
    pattern = create_matcher("Hello {name}")
    match = pattern.match("hello world")
    assert match is not None
    assert match.groupdict()["name"] == "world"
    no_match = pattern.match("Hello world, how are you?")
    assert no_match is None

    # Optional and matching part
    pattern = create_matcher("Turn on [the] {name}")
    match = pattern.match("turn on the kitchen lights")
    assert match is not None
    assert match.groupdict()["name"] == "kitchen lights"
    match = pattern.match("turn on kitchen lights")
    assert match is not None
    assert match.groupdict()["name"] == "kitchen lights"
    match = pattern.match("turn off kitchen lights")
    assert match is None

    # Two different optional parts, 1 matching part
    pattern = create_matcher("Turn on [the] [a] {name}")
    match = pattern.match("turn on the kitchen lights")
    assert match is not None
    assert match.groupdict()["name"] == "kitchen lights"
    match = pattern.match("turn on kitchen lights")
    assert match is not None
    assert match.groupdict()["name"] == "kitchen lights"
    match = pattern.match("turn on a kitchen light")
    assert match is not None
    assert match.groupdict()["name"] == "kitchen light"

    # Strip plural
    pattern = create_matcher("Turn {name}[s] on")
    match = pattern.match("turn kitchen lights on")
    assert match is not None
    assert match.groupdict()["name"] == "kitchen light"

    # Optional 2 words
    pattern = create_matcher("Turn [the great] {name} on")
    match = pattern.match("turn the great kitchen lights on")
    assert match is not None
    assert match.groupdict()["name"] == "kitchen lights"
    match = pattern.match("turn kitchen lights on")
    assert match is not None
    assert match.groupdict()["name"] == "kitchen lights"
