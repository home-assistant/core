import aiohttp
import asyncio
from pyopenhardwaremonitor.api import OpenHardwareMonitorAPI
from typing import TypedDict
# from .types import DataNode, SensorNode

class DataNode(TypedDict):
    """Describes a node in the data tree."""

    id: int
    Text: str
    Min: str
    Value: str
    Max: str
    ImageURL: str
    Children: list['DataNode'] | None

class SensorNode(TypedDict):
    """Describes a data point node (smallest decendant, with info about their parents)."""

    id: int
    Text: str
    Min: str
    Value: str
    Max: str
    ImageURL: str
    Path: list[str]



async def main():
    async with aiohttp.ClientSession() as session:
        api = OpenHardwareMonitorAPI(
            "192.168.90.118", 8085, session=session
        )
        json = await api.get_data()
    sensor_nodes = parse_sensor_nodes(json)
    sensor_data = format_as_dict(sensor_nodes)
    # print(sensor_data.keys())

def parse_sensor_nodes(node: DataNode, path: list[str] | None = None) -> list[SensorNode]:
    result: list[SensorNode] = []
    if path is None:
        path = []
    else:
        path.append(node["Text"])

    if node.get("Children", None):
        for n in node["Children"]:
            sub_nodes = parse_sensor_nodes(n, path.copy())
            result.extend(sub_nodes)
    else:
        # End node...
        sensor = SensorNode(**node)
        del sensor["Children"]
        sensor["Path"] = path

        # print(sensor)
        result.append(sensor)
    return result

def format_as_dict(sensor_nodes: list[SensorNode]) -> dict[str, SensorNode]:
    return { " ".join(n["Path"]): n for n in sensor_nodes}

if __name__ == "__main__":
    # if running on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())


