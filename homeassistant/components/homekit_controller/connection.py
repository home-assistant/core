"""Helpers for managing a pairing with a HomeKit accessory or bridge."""


def get_accessory_information(accessory):
    """Obtain the accessory information service of a HomeKit device."""
    # pylint: disable=import-error
    from homekit.model.services import ServicesTypes
    from homekit.model.characteristics import CharacteristicsTypes

    result = {}
    for service in accessory['services']:
        stype = service['type'].upper()
        if ServicesTypes.get_short(stype) != 'accessory-information':
            continue
        for characteristic in service['characteristics']:
            ctype = CharacteristicsTypes.get_short(characteristic['type'])
            if 'value' in characteristic:
                result[ctype] = characteristic['value']
    return result


def get_bridge_information(accessories):
    """Return the accessory info for the bridge."""
    for accessory in accessories:
        if accessory['aid'] == 1:
            return get_accessory_information(accessory)
    return get_accessory_information(accessories[0])


def get_accessory_name(accessory_info):
    """Return the name field of an accessory."""
    for field in ('name', 'model', 'manufacturer'):
        if field in accessory_info:
            return accessory_info[field]
    return None
