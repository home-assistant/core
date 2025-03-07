from typing import TypedDict


class DataNode(TypedDict):
    """Describes a node in the data tree."""

    id: int
    Text: str
    Min: str
    Value: str
    Max: str
    ImageURL: str
    Children: list["DataNode"] | None


class SensorNode(TypedDict):
    """Describes a data point node (smallest decendant, with info about their parents)."""

    id: int
    Text: str
    Min: str
    Value: str
    Max: str
    ImageURL: str

    Paths: list[str]
    FullName: str
    ComputerName: str
