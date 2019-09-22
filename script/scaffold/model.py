"""Models for scaffolding."""
import attr


@attr.s
class Info:
    """Info about new integration."""

    domain: str = attr.ib()
    name: str = attr.ib()
    codeowner: str = attr.ib()
    requirement: str = attr.ib()
