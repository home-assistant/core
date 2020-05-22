"""Tests for the HomeKit AID manager."""
import os
from zlib import adler32

import pytest

from homeassistant.components.homekit.aidmanager import (
    AccessoryAidStorage,
    get_aid_storage_filename_for_entry_id,
    get_system_unique_id,
)
from homeassistant.helpers import device_registry
from homeassistant.helpers.storage import STORAGE_DIR

from tests.async_mock import patch
from tests.common import MockConfigEntry, mock_device_registry, mock_registry


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_aid_generation(hass, device_reg, entity_reg):
    """Test generating aids."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    light_ent = entity_reg.async_get_or_create(
        "light", "device", "unique_id", device_id=device_entry.id
    )
    light_ent2 = entity_reg.async_get_or_create(
        "light", "device", "other_unique_id", device_id=device_entry.id
    )
    remote_ent = entity_reg.async_get_or_create(
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

    for _ in range(0, 2):
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent.entity_id)
            == 1692141785
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent2.entity_id)
            == 2732133210
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(remote_ent.entity_id)
            == 1867188557
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id("remote.has_no_unique_id")
            == 1872038229
        )

    aid_storage.delete_aid(get_system_unique_id(light_ent))
    aid_storage.delete_aid(get_system_unique_id(light_ent2))
    aid_storage.delete_aid(get_system_unique_id(remote_ent))
    aid_storage.delete_aid("non-existant-one")

    for _ in range(0, 2):
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent.entity_id)
            == 1692141785
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent2.entity_id)
            == 2732133210
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(remote_ent.entity_id)
            == 1867188557
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id("remote.has_no_unique_id")
            == 1872038229
        )


async def test_aid_adler32_collision(hass, device_reg, entity_reg):
    """Test generating aids."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    with patch(
        "homeassistant.components.homekit.aidmanager.AccessoryAidStorage.async_schedule_save"
    ):
        aid_storage = AccessoryAidStorage(hass, config_entry)
    await aid_storage.async_initialize()

    seen_aids = set()

    for unique_id in range(0, 202):
        ent = entity_reg.async_get_or_create(
            "light", "device", unique_id, device_id=device_entry.id
        )
        hass.states.async_set(ent.entity_id, "on")
        aid = aid_storage.get_or_allocate_aid_for_entity_id(ent.entity_id)
        assert aid not in seen_aids
        seen_aids.add(aid)


async def test_aid_generation_no_unique_ids_handles_collision(
    hass, device_reg, entity_reg
):
    """Test colliding aids is stable."""
    config_entry = MockConfigEntry(domain="test", data={})
    aid_storage = AccessoryAidStorage(hass, config_entry)
    await aid_storage.async_initialize()

    seen_aids = set()
    collisions = []

    for light_id in range(0, 220):
        entity_id = f"light.light{light_id}"
        hass.states.async_set(entity_id, "on")
        expected_aid = adler32(entity_id.encode("utf-8"))
        aid = aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
        if aid != expected_aid:
            collisions.append(entity_id)

        assert aid not in seen_aids
        seen_aids.add(aid)

    assert collisions == [
        "light.light201",
        "light.light202",
        "light.light203",
        "light.light204",
        "light.light205",
        "light.light206",
        "light.light207",
        "light.light208",
        "light.light209",
        "light.light211",
        "light.light212",
        "light.light213",
        "light.light214",
        "light.light215",
        "light.light216",
        "light.light217",
        "light.light218",
        "light.light219",
    ]

    assert aid_storage.allocations == {
        "light.light0": 514851983,
        "light.light1": 514917520,
        "light.light10": 594609344,
        "light.light100": 677446896,
        "light.light101": 677512433,
        "light.light102": 677577970,
        "light.light103": 677643507,
        "light.light104": 677709044,
        "light.light105": 677774581,
        "light.light106": 677840118,
        "light.light107": 677905655,
        "light.light108": 677971192,
        "light.light109": 678036729,
        "light.light11": 594674881,
        "light.light110": 677577969,
        "light.light111": 677643506,
        "light.light112": 677709043,
        "light.light113": 677774580,
        "light.light114": 677840117,
        "light.light115": 677905654,
        "light.light116": 677971191,
        "light.light117": 678036728,
        "light.light118": 678102265,
        "light.light119": 678167802,
        "light.light12": 594740418,
        "light.light120": 677709042,
        "light.light121": 677774579,
        "light.light122": 677840116,
        "light.light123": 677905653,
        "light.light124": 677971190,
        "light.light125": 678036727,
        "light.light126": 678102264,
        "light.light127": 678167801,
        "light.light128": 678233338,
        "light.light129": 678298875,
        "light.light13": 594805955,
        "light.light130": 677840115,
        "light.light131": 677905652,
        "light.light132": 677971189,
        "light.light133": 678036726,
        "light.light134": 678102263,
        "light.light135": 678167800,
        "light.light136": 678233337,
        "light.light137": 678298874,
        "light.light138": 678364411,
        "light.light139": 678429948,
        "light.light14": 594871492,
        "light.light140": 677971188,
        "light.light141": 678036725,
        "light.light142": 678102262,
        "light.light143": 678167799,
        "light.light144": 678233336,
        "light.light145": 678298873,
        "light.light146": 678364410,
        "light.light147": 678429947,
        "light.light148": 678495484,
        "light.light149": 678561021,
        "light.light15": 594937029,
        "light.light150": 678102261,
        "light.light151": 678167798,
        "light.light152": 678233335,
        "light.light153": 678298872,
        "light.light154": 678364409,
        "light.light155": 678429946,
        "light.light156": 678495483,
        "light.light157": 678561020,
        "light.light158": 678626557,
        "light.light159": 678692094,
        "light.light16": 595002566,
        "light.light160": 678233334,
        "light.light161": 678298871,
        "light.light162": 678364408,
        "light.light163": 678429945,
        "light.light164": 678495482,
        "light.light165": 678561019,
        "light.light166": 678626556,
        "light.light167": 678692093,
        "light.light168": 678757630,
        "light.light169": 678823167,
        "light.light17": 595068103,
        "light.light170": 678364407,
        "light.light171": 678429944,
        "light.light172": 678495481,
        "light.light173": 678561018,
        "light.light174": 678626555,
        "light.light175": 678692092,
        "light.light176": 678757629,
        "light.light177": 678823166,
        "light.light178": 678888703,
        "light.light179": 678954240,
        "light.light18": 595133640,
        "light.light180": 678495480,
        "light.light181": 678561017,
        "light.light182": 678626554,
        "light.light183": 678692091,
        "light.light184": 678757628,
        "light.light185": 678823165,
        "light.light186": 678888702,
        "light.light187": 678954239,
        "light.light188": 679019776,
        "light.light189": 679085313,
        "light.light19": 595199177,
        "light.light190": 678626553,
        "light.light191": 678692090,
        "light.light192": 678757627,
        "light.light193": 678823164,
        "light.light194": 678888701,
        "light.light195": 678954238,
        "light.light196": 679019775,
        "light.light197": 679085312,
        "light.light198": 679150849,
        "light.light199": 679216386,
        "light.light2": 514983057,
        "light.light20": 594740417,
        "light.light200": 677643505,
        "light.light201": 1682157970,
        "light.light202": 1665380351,
        "light.light203": 1648602732,
        "light.light204": 1631825113,
        "light.light205": 1615047494,
        "light.light206": 1598269875,
        "light.light207": 1581492256,
        "light.light208": 1833156541,
        "light.light209": 1816378922,
        "light.light21": 594805954,
        "light.light210": 677774578,
        "light.light211": 1614900399,
        "light.light212": 1631678018,
        "light.light213": 1648455637,
        "light.light214": 1531012304,
        "light.light215": 1547789923,
        "light.light216": 1564567542,
        "light.light217": 1581345161,
        "light.light218": 1732343732,
        "light.light219": 1749121351,
        "light.light22": 594871491,
        "light.light23": 594937028,
        "light.light24": 595002565,
        "light.light25": 595068102,
        "light.light26": 595133639,
        "light.light27": 595199176,
        "light.light28": 595264713,
        "light.light29": 595330250,
        "light.light3": 515048594,
        "light.light30": 594871490,
        "light.light31": 594937027,
        "light.light32": 595002564,
        "light.light33": 595068101,
        "light.light34": 595133638,
        "light.light35": 595199175,
        "light.light36": 595264712,
        "light.light37": 595330249,
        "light.light38": 595395786,
        "light.light39": 595461323,
        "light.light4": 515114131,
        "light.light40": 595002563,
        "light.light41": 595068100,
        "light.light42": 595133637,
        "light.light43": 595199174,
        "light.light44": 595264711,
        "light.light45": 595330248,
        "light.light46": 595395785,
        "light.light47": 595461322,
        "light.light48": 595526859,
        "light.light49": 595592396,
        "light.light5": 515179668,
        "light.light50": 595133636,
        "light.light51": 595199173,
        "light.light52": 595264710,
        "light.light53": 595330247,
        "light.light54": 595395784,
        "light.light55": 595461321,
        "light.light56": 595526858,
        "light.light57": 595592395,
        "light.light58": 595657932,
        "light.light59": 595723469,
        "light.light6": 515245205,
        "light.light60": 595264709,
        "light.light61": 595330246,
        "light.light62": 595395783,
        "light.light63": 595461320,
        "light.light64": 595526857,
        "light.light65": 595592394,
        "light.light66": 595657931,
        "light.light67": 595723468,
        "light.light68": 595789005,
        "light.light69": 595854542,
        "light.light7": 515310742,
        "light.light70": 595395782,
        "light.light71": 595461319,
        "light.light72": 595526856,
        "light.light73": 595592393,
        "light.light74": 595657930,
        "light.light75": 595723467,
        "light.light76": 595789004,
        "light.light77": 595854541,
        "light.light78": 595920078,
        "light.light79": 595985615,
        "light.light8": 515376279,
        "light.light80": 595526855,
        "light.light81": 595592392,
        "light.light82": 595657929,
        "light.light83": 595723466,
        "light.light84": 595789003,
        "light.light85": 595854540,
        "light.light86": 595920077,
        "light.light87": 595985614,
        "light.light88": 596051151,
        "light.light89": 596116688,
        "light.light9": 515441816,
        "light.light90": 595657928,
        "light.light91": 595723465,
        "light.light92": 595789002,
        "light.light93": 595854539,
        "light.light94": 595920076,
        "light.light95": 595985613,
        "light.light96": 596051150,
        "light.light97": 596116687,
        "light.light98": 596182224,
        "light.light99": 596247761,
    }

    await aid_storage.async_save()
    await hass.async_block_till_done()

    aid_storage = AccessoryAidStorage(hass, config_entry)
    await aid_storage.async_initialize()

    assert aid_storage.allocations == {
        "light.light0": 514851983,
        "light.light1": 514917520,
        "light.light10": 594609344,
        "light.light100": 677446896,
        "light.light101": 677512433,
        "light.light102": 677577970,
        "light.light103": 677643507,
        "light.light104": 677709044,
        "light.light105": 677774581,
        "light.light106": 677840118,
        "light.light107": 677905655,
        "light.light108": 677971192,
        "light.light109": 678036729,
        "light.light11": 594674881,
        "light.light110": 677577969,
        "light.light111": 677643506,
        "light.light112": 677709043,
        "light.light113": 677774580,
        "light.light114": 677840117,
        "light.light115": 677905654,
        "light.light116": 677971191,
        "light.light117": 678036728,
        "light.light118": 678102265,
        "light.light119": 678167802,
        "light.light12": 594740418,
        "light.light120": 677709042,
        "light.light121": 677774579,
        "light.light122": 677840116,
        "light.light123": 677905653,
        "light.light124": 677971190,
        "light.light125": 678036727,
        "light.light126": 678102264,
        "light.light127": 678167801,
        "light.light128": 678233338,
        "light.light129": 678298875,
        "light.light13": 594805955,
        "light.light130": 677840115,
        "light.light131": 677905652,
        "light.light132": 677971189,
        "light.light133": 678036726,
        "light.light134": 678102263,
        "light.light135": 678167800,
        "light.light136": 678233337,
        "light.light137": 678298874,
        "light.light138": 678364411,
        "light.light139": 678429948,
        "light.light14": 594871492,
        "light.light140": 677971188,
        "light.light141": 678036725,
        "light.light142": 678102262,
        "light.light143": 678167799,
        "light.light144": 678233336,
        "light.light145": 678298873,
        "light.light146": 678364410,
        "light.light147": 678429947,
        "light.light148": 678495484,
        "light.light149": 678561021,
        "light.light15": 594937029,
        "light.light150": 678102261,
        "light.light151": 678167798,
        "light.light152": 678233335,
        "light.light153": 678298872,
        "light.light154": 678364409,
        "light.light155": 678429946,
        "light.light156": 678495483,
        "light.light157": 678561020,
        "light.light158": 678626557,
        "light.light159": 678692094,
        "light.light16": 595002566,
        "light.light160": 678233334,
        "light.light161": 678298871,
        "light.light162": 678364408,
        "light.light163": 678429945,
        "light.light164": 678495482,
        "light.light165": 678561019,
        "light.light166": 678626556,
        "light.light167": 678692093,
        "light.light168": 678757630,
        "light.light169": 678823167,
        "light.light17": 595068103,
        "light.light170": 678364407,
        "light.light171": 678429944,
        "light.light172": 678495481,
        "light.light173": 678561018,
        "light.light174": 678626555,
        "light.light175": 678692092,
        "light.light176": 678757629,
        "light.light177": 678823166,
        "light.light178": 678888703,
        "light.light179": 678954240,
        "light.light18": 595133640,
        "light.light180": 678495480,
        "light.light181": 678561017,
        "light.light182": 678626554,
        "light.light183": 678692091,
        "light.light184": 678757628,
        "light.light185": 678823165,
        "light.light186": 678888702,
        "light.light187": 678954239,
        "light.light188": 679019776,
        "light.light189": 679085313,
        "light.light19": 595199177,
        "light.light190": 678626553,
        "light.light191": 678692090,
        "light.light192": 678757627,
        "light.light193": 678823164,
        "light.light194": 678888701,
        "light.light195": 678954238,
        "light.light196": 679019775,
        "light.light197": 679085312,
        "light.light198": 679150849,
        "light.light199": 679216386,
        "light.light2": 514983057,
        "light.light20": 594740417,
        "light.light200": 677643505,
        "light.light201": 1682157970,
        "light.light202": 1665380351,
        "light.light203": 1648602732,
        "light.light204": 1631825113,
        "light.light205": 1615047494,
        "light.light206": 1598269875,
        "light.light207": 1581492256,
        "light.light208": 1833156541,
        "light.light209": 1816378922,
        "light.light21": 594805954,
        "light.light210": 677774578,
        "light.light211": 1614900399,
        "light.light212": 1631678018,
        "light.light213": 1648455637,
        "light.light214": 1531012304,
        "light.light215": 1547789923,
        "light.light216": 1564567542,
        "light.light217": 1581345161,
        "light.light218": 1732343732,
        "light.light219": 1749121351,
        "light.light22": 594871491,
        "light.light23": 594937028,
        "light.light24": 595002565,
        "light.light25": 595068102,
        "light.light26": 595133639,
        "light.light27": 595199176,
        "light.light28": 595264713,
        "light.light29": 595330250,
        "light.light3": 515048594,
        "light.light30": 594871490,
        "light.light31": 594937027,
        "light.light32": 595002564,
        "light.light33": 595068101,
        "light.light34": 595133638,
        "light.light35": 595199175,
        "light.light36": 595264712,
        "light.light37": 595330249,
        "light.light38": 595395786,
        "light.light39": 595461323,
        "light.light4": 515114131,
        "light.light40": 595002563,
        "light.light41": 595068100,
        "light.light42": 595133637,
        "light.light43": 595199174,
        "light.light44": 595264711,
        "light.light45": 595330248,
        "light.light46": 595395785,
        "light.light47": 595461322,
        "light.light48": 595526859,
        "light.light49": 595592396,
        "light.light5": 515179668,
        "light.light50": 595133636,
        "light.light51": 595199173,
        "light.light52": 595264710,
        "light.light53": 595330247,
        "light.light54": 595395784,
        "light.light55": 595461321,
        "light.light56": 595526858,
        "light.light57": 595592395,
        "light.light58": 595657932,
        "light.light59": 595723469,
        "light.light6": 515245205,
        "light.light60": 595264709,
        "light.light61": 595330246,
        "light.light62": 595395783,
        "light.light63": 595461320,
        "light.light64": 595526857,
        "light.light65": 595592394,
        "light.light66": 595657931,
        "light.light67": 595723468,
        "light.light68": 595789005,
        "light.light69": 595854542,
        "light.light7": 515310742,
        "light.light70": 595395782,
        "light.light71": 595461319,
        "light.light72": 595526856,
        "light.light73": 595592393,
        "light.light74": 595657930,
        "light.light75": 595723467,
        "light.light76": 595789004,
        "light.light77": 595854541,
        "light.light78": 595920078,
        "light.light79": 595985615,
        "light.light8": 515376279,
        "light.light80": 595526855,
        "light.light81": 595592392,
        "light.light82": 595657929,
        "light.light83": 595723466,
        "light.light84": 595789003,
        "light.light85": 595854540,
        "light.light86": 595920077,
        "light.light87": 595985614,
        "light.light88": 596051151,
        "light.light89": 596116688,
        "light.light9": 515441816,
        "light.light90": 595657928,
        "light.light91": 595723465,
        "light.light92": 595789002,
        "light.light93": 595854539,
        "light.light94": 595920076,
        "light.light95": 595985613,
        "light.light96": 596051150,
        "light.light97": 596116687,
        "light.light98": 596182224,
        "light.light99": 596247761,
    }

    aidstore = get_aid_storage_filename_for_entry_id(config_entry.entry_id)
    aid_storage_path = hass.config.path(STORAGE_DIR, aidstore)
    if await hass.async_add_executor_job(os.path.exists, aid_storage_path):
        await hass.async_add_executor_job(os.unlink, aid_storage_path)
