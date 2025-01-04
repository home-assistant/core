"""Contains classes to represent ScRpi responses and other objects."""

from dataclasses import dataclass
from typing import Any, Self

from mashumaro.mixins.orjson import DataClassORJSONMixin


class BaseModel(DataClassORJSONMixin):
    """Base model for all ScRpi models.

    Among other methods, DataClassORJSONMixin provides from_dict to serialize dict objects into dataclasses.
    """


@dataclass()
class Device(BaseModel):
    """Object holding all information of ScRpi."""

    number_of_led: int

    # TOD: add section attribute

    def update_from_dict(self, data: dict[str, Any]) -> Self:
        """Return Device object from ScRpi API response.

        Args:
        ----
            data: Update the device object with the data received from a
                ScRpi device API.

        Returns:
        -------
            The updated Device object

        """
        return self
