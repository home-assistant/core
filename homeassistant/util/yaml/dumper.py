"""Custom dumper and representers."""
from collections import OrderedDict
from typing import Any

import yaml

from .objects import Input, NodeDictClass, NodeListClass, NodeStrClass

# mypy: allow-untyped-calls, no-warn-return-any


try:
    from yaml import CSafeDumper as FastestAvailableSafeDumper
except ImportError:
    from yaml import (  # type: ignore[assignment]
        SafeDumper as FastestAvailableSafeDumper,
    )


def dump(_dict: dict | list) -> str:
    """Dump YAML to a string and remove null."""
    return yaml.dump(
        _dict,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        Dumper=FastestAvailableSafeDumper,
    ).replace(": null\n", ":\n")


def save_yaml(path: str, data: dict) -> None:
    """Save YAML to a file."""
    # Dump before writing to not truncate the file if dumping fails
    str_data = dump(data)
    with open(path, "w", encoding="utf-8") as outfile:
        outfile.write(str_data)


# From: https://gist.github.com/miracle2k/3184458
def represent_odict(  # type: ignore[no-untyped-def]
    dumper, tag, mapping, flow_style=None
) -> yaml.MappingNode:
    """Like BaseRepresenter.represent_mapping but does not issue the sort()."""
    value: list = []
    node = yaml.MappingNode(tag, value, flow_style=flow_style)
    if dumper.alias_key is not None:
        dumper.represented_objects[dumper.alias_key] = node
    best_style = True
    if hasattr(mapping, "items"):
        mapping = mapping.items()
    for item_key, item_value in mapping:
        node_key = dumper.represent_data(item_key)
        node_value = dumper.represent_data(item_value)
        if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, yaml.ScalarNode) and not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if dumper.default_flow_style is not None:
            node.flow_style = dumper.default_flow_style
        else:
            node.flow_style = best_style
    return node


def add_representer(klass: Any, representer: Any) -> None:
    """Add to representer to the dumper."""
    FastestAvailableSafeDumper.add_representer(klass, representer)


add_representer(
    OrderedDict,
    lambda dumper, value: represent_odict(dumper, "tag:yaml.org,2002:map", value),
)

add_representer(
    NodeDictClass,
    lambda dumper, value: represent_odict(dumper, "tag:yaml.org,2002:map", value),
)

add_representer(
    NodeListClass,
    lambda dumper, value: dumper.represent_sequence("tag:yaml.org,2002:seq", value),
)

add_representer(
    NodeStrClass,
    lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:str", str(value)),
)

add_representer(
    Input,
    lambda dumper, value: dumper.represent_scalar("!input", value.name),
)
