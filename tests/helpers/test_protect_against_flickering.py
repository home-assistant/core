from unittest.mock import patch
from homeassistant.helpers.protect_against_flickering import _Data, steady
from homeassistant.setup import async_setup_component
import asyncio


def counted_sleep():
    async def sleep(*args):
        sleep.counter = sleep.counter + 1
    sleep.counter = 0
    return sleep


async def no_sleep(*args):
    assert False


async def test_data_init():
    assert _Data(2).last_update_attempt is not None
    assert _Data(4).min_cycle_duration == 4


async def test_basic():
    @steady(("protected",))
    class ObjectToTest:
        async def protected(self, result=None):
            return result

    o = ObjectToTest()
    with patch("asyncio.sleep", no_sleep):
        assert await o.protected("called")
    sleep = counted_sleep()
    with patch("asyncio.sleep", sleep):
        assert await o.protected("called")
    assert sleep.counter == 1
    assert hasattr(o, "_steady_decorator")


async def test_shared():
    @steady(("protected_1", "protected_2"))
    class ObjectToTest:
        async def protected_1(self, result=None):
            return result

        async def protected_2(self, result=None):
            return result

    o = ObjectToTest()
    with patch("asyncio.sleep", no_sleep):
        assert await o.protected_1("called")
    sleep = counted_sleep()
    with patch("asyncio.sleep", sleep):
        assert await o.protected_2("called")
    assert sleep.counter == 1


async def test_dropping_oldest():
    def monotonic_fake_timer():
        time = getattr(monotonic_fake_timer, "time", 20)
        setattr(monotonic_fake_timer, "time", time + 5)
        return time

    @steady(("protected",))
    class ObjectToTest:
        async def protected(self, result=None):
            return result

    with patch("time.time", monotonic_fake_timer):
        o = ObjectToTest()
        with patch("asyncio.sleep", no_sleep):
            assert await o.protected("called")

        total_count = 10
        counter = asyncio.Semaphore(value=total_count)
        lock = asyncio.Semaphore(value=total_count)
        await asyncio.gather(*(counter.acquire() for _ in range(total_count)),
                             *(lock.acquire() for _ in range(total_count)))

        async def locked_sleep(*args):
            counter.release()
            await lock.acquire()

        with patch("asyncio.sleep", locked_sleep):
            results = tuple(asyncio.ensure_future(o.protected(i))
                            for i in range(total_count))
            await asyncio.gather(*(counter.acquire()
                                   for _ in range(total_count)))
            for _ in range(total_count):
                lock.release()
            for result in results:
                assert await result in {None, 9}


async def test_independent_instances():
    @steady(("protected",))
    class ObjectToTest:
        async def protected(self, result=None):
            return result
    o1 = ObjectToTest()
    o2 = ObjectToTest()
    with patch("asyncio.sleep", no_sleep):
        assert await o1.protected("called")
        assert await o2.protected("called")
    sleep = counted_sleep()
    with patch("asyncio.sleep", sleep):
        assert await o1.protected("called")
        assert await o2.protected("called")
    assert sleep.counter == 2
