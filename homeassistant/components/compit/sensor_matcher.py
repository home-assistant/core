"""Sensor matcher for matching sensors based on parameters and values."""

from compit_inext_api import Param, Parameter

from homeassistant.const import Platform


class SensorMatcher:
    """Class for matching sensors based on parameters and values."""

    @staticmethod
    def get_platform(parameter: Parameter, value: Param | None) -> Platform | None:
        """Get the platform based on the parameter and value."""
        if value is None or value.hidden:
            return None
        if parameter.readWrite == "R":
            return Platform.SENSOR
        if parameter.min_value is not None and parameter.max_value is not None:
            return Platform.NUMBER
        if parameter.details is not None:
            return Platform.SELECT
        return None
