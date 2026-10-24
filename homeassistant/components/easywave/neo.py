"""Helpers for Easywave neo sensor capabilities."""

from easywave_home_control.codec.sensors import SensorLearnPayload


def sensor_learn_capabilities(capabilities: int) -> SensorLearnPayload:
    """Interpret a stored capability mask via the library codec.

    The persisted config value is the wire capability bitfield; semantic
    accessors (temperature/humidity) live on ``SensorLearnPayload``.
    """
    return SensorLearnPayload(
        version=0,
        has_battery=False,
        battery_level=0,
        capabilities=int(capabilities),
    )
