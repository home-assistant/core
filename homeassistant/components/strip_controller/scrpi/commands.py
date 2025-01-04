"""ScRpi commands, see https://github.com/brunopk/sc-rpi/blob/master/doc/commands.md."""

from dataclasses import dataclass, field

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class Command(DataClassJSONMixin):
    """Used to represent ScRpi commands.

    DataClassJSONMixin provides to_dict method among other methods.
    """

    name: str


@dataclass
class Status(Command):
    """Represent the status command."""

    name: str = field(default="status", init=False)
