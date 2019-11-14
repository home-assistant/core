import collections
import logging

_LOGGER = logging.getLogger(__name__)


def dict_merge(dct, merge_dct):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.

    Args:
        dct (dict) onto which the merge is executed
        merge_dct (dict): dct merged into dct

    Returns:
        dict: updated dict
    """
    try:
        for k, v in merge_dct.items():
            _LOGGER.debug(str(k) + ": " + str(v))
            if k in dct:
                if isinstance(merge_dct[k], dict):
                    _LOGGER.debug(
                        str(k)
                        + " this is already in ais config, checking if we should merge..."
                    )
                    if v != {}:
                        if isinstance(merge_dct[k], collections.Mapping) or isinstance(
                            merge_dct[k], collections.OrderedDict
                        ):
                            _LOGGER.debug(
                                "isinstance collection, we are going to recursive merge ... "
                            )
                            dct[k] = dict_merge(dct[k], merge_dct[k])
                            _LOGGER.debug("After merge, len: " + str(len(dct)))
                    else:
                        _LOGGER.debug("dct is empty, no need to merge ")
                else:
                    if str(k) in ["automation", "script"]:
                        # concatenate the Nodes, type -> homeassistant.util.yaml.NodeListClass
                        dct[k] = dct[k] + merge_dct[k]
                    else:
                        _LOGGER.debug(
                            str(k)
                            + " new value: "
                            + str(v)
                            + " overwriting the ais dom value: "
                            + str(dct[k])
                        )
                        dct[k] = merge_dct[k]
            else:
                if k != "discovery":
                    dct[k] = merge_dct[k]
                    _LOGGER.debug(
                        str(k)
                        + " this was not in ais config - we are going to include it"
                    )
                else:
                    _LOGGER.debug(str(k) + " discovery is disabled ")
    except Exception as e:
        _LOGGER.error("Merge configurations problem: " + str(e))
    return dct
