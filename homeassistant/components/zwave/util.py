"""Zwave util methods."""
import logging

_LOGGER = logging.getLogger(__name__)


def value_handler(value, method=None, class_id=None, index=None,
                  label=None, data=None, member=None, instance=None,
                  **kwargs):
    """Get the values for a given command_class with arguments.

    May only be used inside callback.

    """
    values = []
    if class_id is None:
        values.extend(value.node.get_values(**kwargs).values())
    else:
        if not isinstance(class_id, list):
            class_id = [class_id]
        for cid in class_id:
            values.extend(value.node.get_values(
                class_id=cid, **kwargs).values())
    _LOGGER.debug('method=%s, class_id=%s, index=%s, label=%s, data=%s,'
                  ' member=%s, instance=%d, kwargs=%s',
                  method, class_id, index, label, data, member, instance,
                  kwargs)
    _LOGGER.debug('values=%s', values)
    results = None
    for value in values:
        if index is not None and value.index != index:
            continue
        if label is not None:
            label_found = False
            for entry in label:
                if value.label == entry:
                    label_found = True
                    break
            if not label_found:
                continue
        if method == 'set':
            value.data = data
            return
        if data is not None and value.data != data:
            continue
        if instance is not None and value.instance != instance:
            continue
        if member is not None:
            results = getattr(value, member)
        else:
            results = value
        break
    _LOGGER.debug('final result=%s', results)
    return results
