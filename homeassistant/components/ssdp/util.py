"""Util functions used by SSDP."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from defusedxml import ElementTree


# Adapted from http://stackoverflow.com/a/10077069
# to follow the XML to JSON spec
# https://www.xml.com/pub/a/2006/05/31/converting-between-xml-and-json.html
def etree_to_dict(tree: ElementTree) -> dict[str, dict[str, Any] | None]:
    """Convert an ETree object to a dict."""
    # strip namespace
    tag_name = tree.tag[tree.tag.find("}") + 1 :]

    tree_dict: dict[str, dict[str, Any] | None] = {
        tag_name: {} if tree.attrib else None
    }
    children = list(tree)
    if children:
        child_dict: dict[str, list] = defaultdict(list)
        for child in map(etree_to_dict, children):
            for k, val in child.items():
                child_dict[k].append(val)
        tree_dict = {
            tag_name: {k: v[0] if len(v) == 1 else v for k, v in child_dict.items()}
        }
    dict_meta = tree_dict[tag_name]
    if tree.attrib:
        assert dict_meta is not None
        dict_meta.update(("@" + k, v) for k, v in tree.attrib.items())
    if tree.text:
        text = tree.text.strip()
        if children or tree.attrib:
            if text:
                assert dict_meta is not None
                dict_meta["#text"] = text
        else:
            tree_dict[tag_name] = text
    return tree_dict
