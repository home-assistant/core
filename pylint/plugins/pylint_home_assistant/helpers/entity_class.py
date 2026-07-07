"""Helpers for scanning Home Assistant entity class hierarchies."""

from astroid import nodes

from .ast_utils import extended_ancestors

ENTITY_QNAME = "homeassistant.helpers.entity.Entity"


def inherits_from_entity(class_node: nodes.ClassDef) -> bool:
    """Return True if class inherits from ``homeassistant.helpers.entity.Entity``."""
    return any(a.qname() == ENTITY_QNAME for a in extended_ancestors(class_node))


def collect_same_module_ancestor_qnames(module: nodes.Module) -> set[str]:
    """Return qnames of every class used as an ancestor in *module*.

    Used to exempt mixin/abstract bases from entity-class checks: a
    class that another same-module class extends is presumed not to be
    the runtime entity.

    Three limitations fall out of the "same-module" scoping:

    1. A class that is BOTH a same-module base AND directly instantiated
       (e.g. both the base and a subclass passed to async_add_entities)
       is exempted by this filter.
    2. A base defined here but only subclassed from a *different* module
       (e.g. base in sensor.py, subclasses in binary_sensor.py) is NOT
       exempted and would be flagged as if it were a runtime entity.
    3. An abstract-by-convention class with no same-module subclass at
       all is flagged. The checker rule should be disabled for those
       classes after verifying they're never instantiated.
    """
    qnames: set[str] = set()
    for class_node in module.nodes_of_class(nodes.ClassDef):
        for ancestor in extended_ancestors(class_node):
            qnames.add(ancestor.qname())
    return qnames
