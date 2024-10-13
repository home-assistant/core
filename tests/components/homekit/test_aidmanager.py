"""Tests for the HomeKit AID manager."""

import os
from unittest.mock import patch

from fnv_hash_fast import fnv1a_32

from homeassistant.components.homekit.aidmanager import (
    AccessoryAidStorage,
    get_aid_storage_filename_for_entry_id,
    get_system_unique_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import STORAGE_DIR

from tests.common import MockConfigEntry


async def test_aid_generation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test generating aids."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    light_ent = entity_registry.async_get_or_create(
        "light", "device", "unique_id", device_id=device_entry.id
    )
    light_ent2 = entity_registry.async_get_or_create(
        "light", "device", "other_unique_id", device_id=device_entry.id
    )
    remote_ent = entity_registry.async_get_or_create(
        "remote", "device", "unique_id", device_id=device_entry.id
    )
    hass.states.async_set(light_ent.entity_id, "on")
    hass.states.async_set(light_ent2.entity_id, "on")
    hass.states.async_set(remote_ent.entity_id, "on")
    hass.states.async_set("remote.has_no_unique_id", "on")

    with patch(
        "homeassistant.components.homekit.aidmanager.AccessoryAidStorage.async_schedule_save"
    ):
        aid_storage = AccessoryAidStorage(hass, config_entry)
    await aid_storage.async_initialize()

    for _ in range(2):
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent.entity_id)
            == 1953095294
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent2.entity_id)
            == 1975378727
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(remote_ent.entity_id)
            == 3508011530
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id("remote.has_no_unique_id")
            == 1751603975
        )

    aid_storage.delete_aid(get_system_unique_id(light_ent, light_ent.unique_id))
    aid_storage.delete_aid(get_system_unique_id(light_ent2, light_ent2.unique_id))
    aid_storage.delete_aid(get_system_unique_id(remote_ent, remote_ent.unique_id))
    aid_storage.delete_aid("non-existent-one")

    for _ in range(2):
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent.entity_id)
            == 1953095294
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent2.entity_id)
            == 1975378727
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(remote_ent.entity_id)
            == 3508011530
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id("remote.has_no_unique_id")
            == 1751603975
        )


async def test_no_aid_collision(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test generating aids."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    with patch(
        "homeassistant.components.homekit.aidmanager.AccessoryAidStorage.async_schedule_save"
    ):
        aid_storage = AccessoryAidStorage(hass, config_entry)
    await aid_storage.async_initialize()

    seen_aids = set()

    for unique_id in range(202):
        ent = entity_registry.async_get_or_create(
            "light", "device", unique_id, device_id=device_entry.id
        )
        hass.states.async_set(ent.entity_id, "on")
        aid = aid_storage.get_or_allocate_aid_for_entity_id(ent.entity_id)
        assert aid not in seen_aids
        seen_aids.add(aid)


async def test_aid_generation_no_unique_ids_handles_collision(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test colliding aids is stable."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    aid_storage = AccessoryAidStorage(hass, config_entry)
    await aid_storage.async_initialize()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    seen_aids = set()
    collisions = []

    for light_id in range(220):
        entity_id = f"light.light{light_id}"
        hass.states.async_set(entity_id, "on")
        expected_aid = fnv1a_32(entity_id.encode("utf-8"))
        aid = aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
        if aid != expected_aid:
            collisions.append(entity_id)

        assert aid not in seen_aids
        seen_aids.add(aid)

    light_ent = entity_registry.async_get_or_create(
        "light", "device", "unique_id", device_id=device_entry.id
    )
    hass.states.async_set(light_ent.entity_id, "on")
    aid_storage.get_or_allocate_aid_for_entity_id(light_ent.entity_id)

    assert not collisions

    assert aid_storage.allocations == {
        "device.light.unique_id": 1953095294,
        "light.light0": 301577847,
        "light.light1": 284800228,
        "light.light10": 2367138236,
        "light.light100": 2822760292,
        "light.light101": 2839537911,
        "light.light102": 2856315530,
        "light.light103": 2873093149,
        "light.light104": 2755649816,
        "light.light105": 2772427435,
        "light.light106": 2789205054,
        "light.light107": 2805982673,
        "light.light108": 2688539340,
        "light.light109": 2705316959,
        "light.light11": 2383915855,
        "light.light110": 776141037,
        "light.light111": 759363418,
        "light.light112": 742585799,
        "light.light113": 725808180,
        "light.light114": 709030561,
        "light.light115": 692252942,
        "light.light116": 675475323,
        "light.light117": 658697704,
        "light.light118": 641920085,
        "light.light119": 625142466,
        "light.light12": 2400693474,
        "light.light120": 340070038,
        "light.light121": 356847657,
        "light.light122": 306514800,
        "light.light123": 323292419,
        "light.light124": 407180514,
        "light.light125": 423958133,
        "light.light126": 373625276,
        "light.light127": 390402895,
        "light.light128": 474290990,
        "light.light129": 491068609,
        "light.light13": 2417471093,
        "light.light130": 440882847,
        "light.light131": 424105228,
        "light.light132": 474438085,
        "light.light133": 457660466,
        "light.light134": 373772371,
        "light.light135": 356994752,
        "light.light136": 407327609,
        "light.light137": 390549990,
        "light.light138": 575103799,
        "light.light139": 558326180,
        "light.light14": 2300027760,
        "light.light140": 271973824,
        "light.light141": 288751443,
        "light.light142": 305529062,
        "light.light143": 322306681,
        "light.light144": 339084300,
        "light.light145": 355861919,
        "light.light146": 372639538,
        "light.light147": 389417157,
        "light.light148": 406194776,
        "light.light149": 422972395,
        "light.light15": 2316805379,
        "light.light150": 2520321865,
        "light.light151": 2503544246,
        "light.light152": 2486766627,
        "light.light153": 2469989008,
        "light.light154": 2587432341,
        "light.light155": 2570654722,
        "light.light156": 2553877103,
        "light.light157": 2537099484,
        "light.light158": 2654542817,
        "light.light159": 2637765198,
        "light.light16": 2333582998,
        "light.light160": 2621134674,
        "light.light161": 2637912293,
        "light.light162": 2587579436,
        "light.light163": 2604357055,
        "light.light164": 2554024198,
        "light.light165": 2570801817,
        "light.light166": 2520468960,
        "light.light167": 2537246579,
        "light.light168": 2755355626,
        "light.light169": 2772133245,
        "light.light17": 2350360617,
        "light.light170": 2721947483,
        "light.light171": 2705169864,
        "light.light172": 2755502721,
        "light.light173": 2738725102,
        "light.light174": 2789057959,
        "light.light175": 2772280340,
        "light.light176": 2822613197,
        "light.light177": 2805835578,
        "light.light178": 2587726531,
        "light.light179": 2570948912,
        "light.light18": 2501359188,
        "light.light180": 408166252,
        "light.light181": 424943871,
        "light.light182": 441721490,
        "light.light183": 458499109,
        "light.light184": 341055776,
        "light.light185": 357833395,
        "light.light186": 374611014,
        "light.light187": 391388633,
        "light.light188": 542387204,
        "light.light189": 559164823,
        "light.light19": 2518136807,
        "light.light190": 508979061,
        "light.light191": 492201442,
        "light.light192": 475423823,
        "light.light193": 458646204,
        "light.light194": 441868585,
        "light.light195": 425090966,
        "light.light196": 408313347,
        "light.light197": 391535728,
        "light.light198": 643200013,
        "light.light199": 626422394,
        "light.light2": 335133085,
        "light.light20": 522144599,
        "light.light200": 1698935589,
        "light.light201": 1682157970,
        "light.light202": 1665380351,
        "light.light203": 1648602732,
        "light.light204": 1631825113,
        "light.light205": 1615047494,
        "light.light206": 1598269875,
        "light.light207": 1581492256,
        "light.light208": 1833156541,
        "light.light209": 1816378922,
        "light.light21": 505366980,
        "light.light210": 1598122780,
        "light.light211": 1614900399,
        "light.light212": 1631678018,
        "light.light213": 1648455637,
        "light.light214": 1531012304,
        "light.light215": 1547789923,
        "light.light216": 1564567542,
        "light.light217": 1581345161,
        "light.light218": 1732343732,
        "light.light219": 1749121351,
        "light.light22": 555699837,
        "light.light23": 538922218,
        "light.light24": 455034123,
        "light.light25": 438256504,
        "light.light26": 488589361,
        "light.light27": 471811742,
        "light.light28": 387923647,
        "light.light29": 371146028,
        "light.light3": 318355466,
        "light.light30": 421331790,
        "light.light31": 438109409,
        "light.light32": 387776552,
        "light.light33": 404554171,
        "light.light34": 488442266,
        "light.light35": 505219885,
        "light.light36": 454887028,
        "light.light37": 471664647,
        "light.light38": 287110838,
        "light.light39": 303888457,
        "light.light4": 234467371,
        "light.light40": 454048385,
        "light.light41": 437270766,
        "light.light42": 420493147,
        "light.light43": 403715528,
        "light.light44": 521158861,
        "light.light45": 504381242,
        "light.light46": 487603623,
        "light.light47": 470826004,
        "light.light48": 319827433,
        "light.light49": 303049814,
        "light.light5": 217689752,
        "light.light50": 353235576,
        "light.light51": 370013195,
        "light.light52": 386790814,
        "light.light53": 403568433,
        "light.light54": 420346052,
        "light.light55": 437123671,
        "light.light56": 453901290,
        "light.light57": 470678909,
        "light.light58": 219014624,
        "light.light59": 235792243,
        "light.light6": 268022609,
        "light.light60": 2266325427,
        "light.light61": 2249547808,
        "light.light62": 2299880665,
        "light.light63": 2283103046,
        "light.light64": 2333435903,
        "light.light65": 2316658284,
        "light.light66": 2366991141,
        "light.light67": 2350213522,
        "light.light68": 2400546379,
        "light.light69": 2383768760,
        "light.light7": 251244990,
        "light.light70": 554861194,
        "light.light71": 571638813,
        "light.light72": 521305956,
        "light.light73": 538083575,
        "light.light74": 487750718,
        "light.light75": 504528337,
        "light.light76": 454195480,
        "light.light77": 470973099,
        "light.light78": 420640242,
        "light.light79": 437417861,
        "light.light8": 167356895,
        "light.light80": 2735113021,
        "light.light81": 2718335402,
        "light.light82": 2701557783,
        "light.light83": 2684780164,
        "light.light84": 2668002545,
        "light.light85": 2651224926,
        "light.light86": 2634447307,
        "light.light87": 2617669688,
        "light.light88": 2600892069,
        "light.light89": 2584114450,
        "light.light9": 150579276,
        "light.light90": 2634300212,
        "light.light91": 2651077831,
        "light.light92": 2667855450,
        "light.light93": 2684633069,
        "light.light94": 2567189736,
        "light.light95": 2583967355,
        "light.light96": 2600744974,
        "light.light97": 2617522593,
        "light.light98": 2500079260,
        "light.light99": 2516856879,
    }

    await aid_storage.async_save()
    await hass.async_block_till_done()

    with patch("fnv_hash_fast.fnv1a_32", side_effect=Exception):
        aid_storage = AccessoryAidStorage(hass, config_entry)
    await aid_storage.async_initialize()

    assert aid_storage.allocations == {
        "device.light.unique_id": 1953095294,
        "light.light0": 301577847,
        "light.light1": 284800228,
        "light.light10": 2367138236,
        "light.light100": 2822760292,
        "light.light101": 2839537911,
        "light.light102": 2856315530,
        "light.light103": 2873093149,
        "light.light104": 2755649816,
        "light.light105": 2772427435,
        "light.light106": 2789205054,
        "light.light107": 2805982673,
        "light.light108": 2688539340,
        "light.light109": 2705316959,
        "light.light11": 2383915855,
        "light.light110": 776141037,
        "light.light111": 759363418,
        "light.light112": 742585799,
        "light.light113": 725808180,
        "light.light114": 709030561,
        "light.light115": 692252942,
        "light.light116": 675475323,
        "light.light117": 658697704,
        "light.light118": 641920085,
        "light.light119": 625142466,
        "light.light12": 2400693474,
        "light.light120": 340070038,
        "light.light121": 356847657,
        "light.light122": 306514800,
        "light.light123": 323292419,
        "light.light124": 407180514,
        "light.light125": 423958133,
        "light.light126": 373625276,
        "light.light127": 390402895,
        "light.light128": 474290990,
        "light.light129": 491068609,
        "light.light13": 2417471093,
        "light.light130": 440882847,
        "light.light131": 424105228,
        "light.light132": 474438085,
        "light.light133": 457660466,
        "light.light134": 373772371,
        "light.light135": 356994752,
        "light.light136": 407327609,
        "light.light137": 390549990,
        "light.light138": 575103799,
        "light.light139": 558326180,
        "light.light14": 2300027760,
        "light.light140": 271973824,
        "light.light141": 288751443,
        "light.light142": 305529062,
        "light.light143": 322306681,
        "light.light144": 339084300,
        "light.light145": 355861919,
        "light.light146": 372639538,
        "light.light147": 389417157,
        "light.light148": 406194776,
        "light.light149": 422972395,
        "light.light15": 2316805379,
        "light.light150": 2520321865,
        "light.light151": 2503544246,
        "light.light152": 2486766627,
        "light.light153": 2469989008,
        "light.light154": 2587432341,
        "light.light155": 2570654722,
        "light.light156": 2553877103,
        "light.light157": 2537099484,
        "light.light158": 2654542817,
        "light.light159": 2637765198,
        "light.light16": 2333582998,
        "light.light160": 2621134674,
        "light.light161": 2637912293,
        "light.light162": 2587579436,
        "light.light163": 2604357055,
        "light.light164": 2554024198,
        "light.light165": 2570801817,
        "light.light166": 2520468960,
        "light.light167": 2537246579,
        "light.light168": 2755355626,
        "light.light169": 2772133245,
        "light.light17": 2350360617,
        "light.light170": 2721947483,
        "light.light171": 2705169864,
        "light.light172": 2755502721,
        "light.light173": 2738725102,
        "light.light174": 2789057959,
        "light.light175": 2772280340,
        "light.light176": 2822613197,
        "light.light177": 2805835578,
        "light.light178": 2587726531,
        "light.light179": 2570948912,
        "light.light18": 2501359188,
        "light.light180": 408166252,
        "light.light181": 424943871,
        "light.light182": 441721490,
        "light.light183": 458499109,
        "light.light184": 341055776,
        "light.light185": 357833395,
        "light.light186": 374611014,
        "light.light187": 391388633,
        "light.light188": 542387204,
        "light.light189": 559164823,
        "light.light19": 2518136807,
        "light.light190": 508979061,
        "light.light191": 492201442,
        "light.light192": 475423823,
        "light.light193": 458646204,
        "light.light194": 441868585,
        "light.light195": 425090966,
        "light.light196": 408313347,
        "light.light197": 391535728,
        "light.light198": 643200013,
        "light.light199": 626422394,
        "light.light2": 335133085,
        "light.light20": 522144599,
        "light.light200": 1698935589,
        "light.light201": 1682157970,
        "light.light202": 1665380351,
        "light.light203": 1648602732,
        "light.light204": 1631825113,
        "light.light205": 1615047494,
        "light.light206": 1598269875,
        "light.light207": 1581492256,
        "light.light208": 1833156541,
        "light.light209": 1816378922,
        "light.light21": 505366980,
        "light.light210": 1598122780,
        "light.light211": 1614900399,
        "light.light212": 1631678018,
        "light.light213": 1648455637,
        "light.light214": 1531012304,
        "light.light215": 1547789923,
        "light.light216": 1564567542,
        "light.light217": 1581345161,
        "light.light218": 1732343732,
        "light.light219": 1749121351,
        "light.light22": 555699837,
        "light.light23": 538922218,
        "light.light24": 455034123,
        "light.light25": 438256504,
        "light.light26": 488589361,
        "light.light27": 471811742,
        "light.light28": 387923647,
        "light.light29": 371146028,
        "light.light3": 318355466,
        "light.light30": 421331790,
        "light.light31": 438109409,
        "light.light32": 387776552,
        "light.light33": 404554171,
        "light.light34": 488442266,
        "light.light35": 505219885,
        "light.light36": 454887028,
        "light.light37": 471664647,
        "light.light38": 287110838,
        "light.light39": 303888457,
        "light.light4": 234467371,
        "light.light40": 454048385,
        "light.light41": 437270766,
        "light.light42": 420493147,
        "light.light43": 403715528,
        "light.light44": 521158861,
        "light.light45": 504381242,
        "light.light46": 487603623,
        "light.light47": 470826004,
        "light.light48": 319827433,
        "light.light49": 303049814,
        "light.light5": 217689752,
        "light.light50": 353235576,
        "light.light51": 370013195,
        "light.light52": 386790814,
        "light.light53": 403568433,
        "light.light54": 420346052,
        "light.light55": 437123671,
        "light.light56": 453901290,
        "light.light57": 470678909,
        "light.light58": 219014624,
        "light.light59": 235792243,
        "light.light6": 268022609,
        "light.light60": 2266325427,
        "light.light61": 2249547808,
        "light.light62": 2299880665,
        "light.light63": 2283103046,
        "light.light64": 2333435903,
        "light.light65": 2316658284,
        "light.light66": 2366991141,
        "light.light67": 2350213522,
        "light.light68": 2400546379,
        "light.light69": 2383768760,
        "light.light7": 251244990,
        "light.light70": 554861194,
        "light.light71": 571638813,
        "light.light72": 521305956,
        "light.light73": 538083575,
        "light.light74": 487750718,
        "light.light75": 504528337,
        "light.light76": 454195480,
        "light.light77": 470973099,
        "light.light78": 420640242,
        "light.light79": 437417861,
        "light.light8": 167356895,
        "light.light80": 2735113021,
        "light.light81": 2718335402,
        "light.light82": 2701557783,
        "light.light83": 2684780164,
        "light.light84": 2668002545,
        "light.light85": 2651224926,
        "light.light86": 2634447307,
        "light.light87": 2617669688,
        "light.light88": 2600892069,
        "light.light89": 2584114450,
        "light.light9": 150579276,
        "light.light90": 2634300212,
        "light.light91": 2651077831,
        "light.light92": 2667855450,
        "light.light93": 2684633069,
        "light.light94": 2567189736,
        "light.light95": 2583967355,
        "light.light96": 2600744974,
        "light.light97": 2617522593,
        "light.light98": 2500079260,
        "light.light99": 2516856879,
    }

    aidstore = get_aid_storage_filename_for_entry_id(config_entry.entry_id)
    aid_storage_path = hass.config.path(STORAGE_DIR, aidstore)
    if await hass.async_add_executor_job(os.path.exists, aid_storage_path):
        await hass.async_add_executor_job(os.unlink, aid_storage_path)


async def test_handle_unique_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test handling unique id changes."""
    light = entity_registry.async_get_or_create("light", "demo", "old_unique")
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.homekit.aidmanager.AccessoryAidStorage.async_schedule_save"
    ):
        aid_storage = AccessoryAidStorage(hass, config_entry)
    await aid_storage.async_initialize()

    original_aid = aid_storage.get_or_allocate_aid_for_entity_id(light.entity_id)
    assert aid_storage.allocations == {"demo.light.old_unique": 4202023227}

    entity_registry.async_update_entity(light.entity_id, new_unique_id="new_unique")
    await hass.async_block_till_done()

    aid = aid_storage.get_or_allocate_aid_for_entity_id(light.entity_id)
    assert aid == original_aid

    # Verify that the old unique id is removed from the allocations
    # and that the new unique id assumes the old aid
    assert aid_storage.allocations == {"demo.light.new_unique": 4202023227}
