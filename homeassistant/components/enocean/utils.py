"""Hold utility functions."""

import logging
from typing import Union

from enocean.communicators import Communicator
import enocean.utils as lib_utils

import homeassistant.components.enocean as ec  # import DATA_ENOCEAN, ENOCEAN_DONGLE, EnOceanDongle
from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)


def get_communicator_reference(hass: HomeAssistant) -> Union[object, Communicator]:
    """Get a reference to the communicator (dongle/pihat)."""
    enocean_data = hass.data.get(ec.DATA_ENOCEAN, {})
    dongle: ec.EnOceanDongle = enocean_data[ec.ENOCEAN_DONGLE]
    if not dongle:
        LOGGER.error("No EnOcean Dongle configured or available. No teach-in possible.")
        return None
    communicator: Communicator = dongle.communicator
    return communicator


def int_to_list(int_value):
    """Convert integer to list of values."""
    result = []
    while int_value > 0:
        result.append(int_value % 256)
        int_value = int_value // 256
    result.reverse()
    return result


def hex_to_list(hex_value):
    """Convert hexadecimal value to a list of int values."""
    # it FFD97F81 has to be [FF, D9, 7F, 81] => [255, 217, 127, 129]
    result = []
    if hex_value is None:
        return result

    while hex_value > 0:
        result.append(hex_value % 0x100)
        hex_value = hex_value // 256
    result.reverse()
    return result


def get_next_free_sender_id(start_base_id: int, used_base_ids_so_far: list[int]):
    """Depending on the base id of the dongle and already used base IDs, determine the next free one.

    Make usage of eventually existing gaps.
    """
    # print("Base ID given: %02x" % combine_hex(start_base_id))
    # used_base_ids_so_far is a list of lists (list of integer lists)
    # used_ids_as_str = ','.join([to_hex_string(base_id) for base_id in used_base_ids_so_far])
    # print("Used Base IDs so far: %s" % used_ids_as_str)

    communicator_max_base_id = lib_utils.combine_hex(start_base_id) + 127

    # print("Maximum Base ID: %s hex: " % str(communicator_max_base_id), to_hex_string(communicator_max_base_id))

    # is any Base ID used, yet?
    if len(used_base_ids_so_far) == 0:
        # use the start_base_id and return it
        base_id_as_list = int_to_list(start_base_id)
        used_base_ids_so_far.append(base_id_as_list)
        # return start_base_id
        return base_id_as_list

    # sort the ids
    # convert them to integers first
    sorted_used_base_ids_so_far = sorted(
        lib_utils.combine_hex(base_id) for base_id in used_base_ids_so_far
    )
    # used_base_ids_so_far.sort()
    # is there only one used (can't be zero here)
    if len(sorted_used_base_ids_so_far) == 1:
        # nothing to compare. Simply take the next one
        # return hex_to_list(sorted_used_base_ids_so_far[0] + 1)

        # check if the next one is smaller than the allowed limit and within the range of the base id
        possible_next_free_base_id = sorted_used_base_ids_so_far[0] + 1
        if (
            possible_next_free_base_id <= 0xFFFFFFFE
            and possible_next_free_base_id <= communicator_max_base_id
        ):
            return int_to_list(possible_next_free_base_id)

    for index, value in enumerate(sorted_used_base_ids_so_far[:-1]):
        # find a gap
        if (
            sorted_used_base_ids_so_far[index + 1] - sorted_used_base_ids_so_far[index]
            > 1
        ):
            # there is a gap because the difference is bigger than one
            # so use the gap
            next_free_base_id = sorted_used_base_ids_so_far[index] + 1
            next_free_base_id_as_list = int_to_list(next_free_base_id)
            # this is only a copy: no appending & sorting required here
            # sorted_used_base_ids_so_far.append(next_free_base_id_as_list)
            # sorted_used_base_ids_so_far.sort()
            # convert them back to list of integers
            return next_free_base_id_as_list
        else:
            # there is no gap
            # so check the next one
            continue

    # we checked all the used Base IDs
    # now check if the next one is below the allowed limit of 0xFFFFFFFE
    # See (https://www.enocean-alliance.org/wp-content/uploads/2021/03/EURID-v1.2.pdf)
    # used_base_ids_so_far is a list of lists
    # last_used_base_id_as_list = used_base_ids_so_far[-1]
    last_used_base_id = sorted_used_base_ids_so_far[-1]
    next_free_base_id = last_used_base_id + 1
    if (
        next_free_base_id <= 0xFFFFFFFE
        and next_free_base_id <= communicator_max_base_id
    ):
        return int_to_list(next_free_base_id)
    else:
        # there is no Base ID left  # Exception?
        # return None
        raise OverflowError()
