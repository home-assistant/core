"""Nested lookup method to collect alarms."""
from collections import defaultdict

# from six import iteritems

VALUES_LIST = []


def nested_lookup(key, document, wild=False, with_keys=False):
    """Lookup a key in a nested document, return a list of values."""
    if with_keys:
        dd = defaultdict(list)
        for kk, vv in _nested_lookup(key, document, wild=wild, with_keys=with_keys):
            dd[kk].append(vv)
        return dd
    return list(_nested_lookup(key, document, wild=wild, with_keys=with_keys))


def _is_case_insensitive_substring(aa, bb):
    """Return True if `a` is a case insensitive substring of `b`, else False."""
    return str(aa).lower() in str(bb).lower()


def _nested_lookup(key, document, wild=False, with_keys=False):
    """Lookup a key in a nested document, yield a value."""
    if isinstance(document, list):
        for dd in document:
            yield from _nested_lookup(key, dd, wild=wild, with_keys=with_keys)

    if isinstance(document, dict):
        for kk, vv in document.items():
            if key == kk or (wild and _is_case_insensitive_substring(key, kk)):
                if with_keys:
                    yield kk, vv
                else:
                    yield vv
            if isinstance(vv, dict):
                yield from _nested_lookup(key, vv, wild=wild, with_keys=with_keys)
            elif isinstance(vv, list):
                for dd in vv:
                    yield from _nested_lookup(key, dd, wild=wild, with_keys=with_keys)


def get_all_keys(dictionary):
    """Get all keys from a nested dictionary as a List."""

    result_list = []

    def recursion(document):
        if isinstance(document, list):
            for list_items in document:
                recursion(document=list_items)
        elif isinstance(document, dict):
            for key, value in document.items():
                result_list.append(key)
                recursion(document=value)
        # return

    recursion(document=dictionary)
    return result_list


def get_occurrence_of_key(dictionary, key):
    """Get occurrence of a key in a nested dictionary."""
    return _get_occurrence(dictionary=dictionary, item="key", keyword=key)


def get_occurrences_and_values(items, value):
    """Get occurrence of a value in a nested list of dictionary."""
    occurrences = {}
    occurrence = 0
    value_list = []

    for item in items:
        occurrence_result, values = _get_occurrence_with_values(
            dictionary=item, item="value", keyword=value
        )
        occurrence = occurrence + occurrence_result
        if occurrence_result:
            value_list.extend(values)

    occurrences[value] = {"occurrences": occurrence, "values": value_list}

    return occurrences


def _get_occurrence_with_values(dictionary, item, keyword):
    occurrence = [0]

    result_recursion = _recursion(dictionary, item, keyword, occurrence, True)

    global VALUES_LIST
    VALUES_LIST = []

    return occurrence[0], result_recursion


def get_occurrence_of_value(dictionary, value):
    """Get occurrence of a value in a nested dictionary."""

    return _get_occurrence(dictionary=dictionary, item="value", keyword=value)


def _recursion(dictionary, item, keyword, occurrence, with_values=False):

    global VALUES_LIST

    if item == "key":
        if dictionary.get(keyword) is not None:
            occurrence[0] += 1
    elif keyword in list(dictionary.values()):
        occurrence[0] += list(dictionary.values()).count(keyword)
        if with_values:
            VALUES_LIST.append(dictionary)
    for value in dictionary.items():
        if isinstance(value, dict):
            _recursion(value, item, keyword, occurrence, with_values)
        elif isinstance(value, list):
            for list_items in value:
                if hasattr(list_items, "items"):
                    _recursion(list_items, item, keyword, occurrence, with_values)
                elif list_items == keyword:
                    occurrence[0] += 1 if item == "value" else 0

    if VALUES_LIST:
        return VALUES_LIST


def _get_occurrence(dictionary, item, keyword):
    """Get occurrence of a key or value in a nested dictionary."""
    occurrence = [0]
    _recursion(dictionary, item, keyword, occurrence)

    global VALUES_LIST
    VALUES_LIST = []

    return occurrence[0]
