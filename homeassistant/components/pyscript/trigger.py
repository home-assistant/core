"""Implements all the trigger logic."""

import asyncio
import datetime
import locale
import logging
import math
import re
import time

from homeassistant.components.pyscript.eval import AstEval
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
import homeassistant.helpers.sun as sun
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


def dt_now():
    """Return current time."""
    return datetime.datetime.now()


def isleap(year):
    """Return True or False if year is a leap year."""
    return (year % 4) == 0 and (year % 100) != 0 or (year % 400) == 0


def days_in_mon(month, year):
    """Return numbers of days in month month of year year, 1 <= month <= 12."""
    dom = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    month -= 1
    if month < 0 or month >= len(dom):
        return -1
    if (month == 1) and isleap(year):
        return dom[month] + 1
    return dom[month]


def days_between(month1, day1, year1, month2, day2, year2):
    """Calculate the number of days in between the two dates."""
    delta = datetime.date(year2, month2, day2) - datetime.date(year1, month1, day1)
    return round(delta.days)


def cron_ge(cron, fld, curr):
    """Return the next value which is >= curr and matches cron[fld]."""
    min_ge = 1000
    ret = 1000

    if cron[fld] == "*":
        return curr
    for elt in cron[fld].split(","):
        rng = elt.split("-")
        if len(rng) == 2:
            rng0, rng1 = [int(rng[0]), int(rng[1])]
            if rng0 < ret:
                ret = rng0
            if rng0 > rng1:
                # wrap case
                if curr >= rng0 or curr < rng1:
                    return curr
            else:
                if rng0 <= curr <= rng1:
                    return curr
                if curr <= rng0 < min_ge:
                    min_ge = rng0
        elif len(rng) == 1:
            rng0 = int(rng[0])
            if curr == rng0:
                return curr
            if rng0 < ret:
                ret = rng0
            if curr <= rng0 < min_ge:
                min_ge = rng0
        else:
            _LOGGER.warning("can't parse field %s in cron entry %s", elt, cron[fld])
            return curr
    if min_ge < 1000:
        return min_ge
    return ret


def parse_time_offset(offset_str):
    """Parse a time offset."""
    match = re.split(r"([-+]?\s*\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(\w*)", offset_str)
    scale = 1
    value = 0
    if len(match) == 4:
        value = float(match[1].replace(" ", ""))
        if match[2] == "m" or match[2] == "min" or match[2] == "minutes":
            scale = 60
        elif match[2] == "h" or match[2] == "hr" or match[2] == "hours":
            scale = 60 * 60
        elif match[2] == "d" or match[2] == "day" or match[2] == "days":
            scale = 60 * 60 * 24
        elif match[2] == "w" or match[2] == "week" or match[2] == "weeks":
            scale = 60 * 60 * 24 * 7
    return value * scale


class TrigTime:
    """Class for trigger time functions."""

    def __init__(self, hass=None, handler_func=None):
        """Create a new TrigTime."""
        self.hass = hass

        def wait_until_factory(ast_ctx):
            """Return wapper to call to astFunction with the ast context."""

            async def wait_until_call(*arg, **kw):
                return await self.wait_until(ast_ctx, *arg, **kw)

            return wait_until_call

        self.ast_funcs = {
            "task.wait_until": wait_until_factory,
        }
        handler_func.register_ast(self.ast_funcs)

        #
        # Mappings of day of week name to number, using US convention of sun is 0.
        # Initialized based on locale at startup.
        #
        self.dow2int = {}
        for i in range(0, 7):
            self.dow2int[
                locale.nl_langinfo(getattr(locale, f"ABDAY_{i+1}")).lower()
            ] = i
            self.dow2int[locale.nl_langinfo(getattr(locale, f"DAY_{i+1}")).lower()] = i

    async def wait_until(
        self,
        ast_ctx,
        state_trigger=None,
        state_check_now=True,
        time_trigger=None,
        event_trigger=None,
        timeout=None,
        **kwargs,
    ):
        """Wait for zero or more triggers, until an optional timeout."""
        if state_trigger is None and time_trigger is None and event_trigger is None:
            if timeout is not None:
                await asyncio.sleep(timeout)
                return {"trigger_type": "timeout"}
            return {"trigger_type": "none"}
        state_trig_ident = None
        state_trig_expr = None
        event_trig_expr = None
        notify_q = asyncio.Queue(0)
        if state_trigger is not None:
            state_trig_expr = AstEval(
                f"{ast_ctx.name} wait_until state_trigger",
                ast_ctx.global_sym_table,
                state_func=ast_ctx.state,
                event_func=ast_ctx.event,
                handler_func=ast_ctx.handler,
            )
            ast_ctx.handler.install_ast_funcs(state_trig_expr)
            state_trig_expr.parse(state_trigger)
            #
            # check straight away to see if the condition is met (to avoid race conditions)
            #
            if await state_trig_expr.eval():
                return {"trigger_type": "state"}
            state_trig_ident = state_trig_expr.ast_get_names()
            _LOGGER.debug(
                "trigger %s wait_until: watching vars %s",
                ast_ctx.name,
                state_trig_ident,
            )
            if len(state_trig_ident) > 0:
                ast_ctx.state.notify_add(state_trig_ident, notify_q)
        if event_trigger is not None:
            if isinstance(event_trigger, str):
                event_trigger = [event_trigger]
            ast_ctx.event.notify_add(event_trigger[0], notify_q)
            if len(event_trigger) > 1:
                event_trig_expr = AstEval(
                    f"trigger {ast_ctx.name} wait_until event_trigger",
                    ast_ctx.global_sym_table,
                    state_func=ast_ctx.state,
                    event_func=ast_ctx.event,
                    handler_func=ast_ctx.handler,
                )
                ast_ctx.handler.install_ast_funcs(event_trig_expr)
                event_trig_expr.parse(event_trigger[1])
        time0 = time.monotonic()
        while 1:
            this_timeout = None
            if time_trigger is not None:
                now = dt_now()
                time_next = self.timer_trigger_next(time_trigger, now)
                _LOGGER.debug(
                    "trigger %s wait_until time_next = %s, now = %s",
                    ast_ctx.name,
                    time_next,
                    now,
                )
                if time_next is not None:
                    this_timeout = (time_next - now).total_seconds()
            if timeout is not None:
                time_left = time0 + timeout - time.monotonic()
                if time_left <= 0:
                    ret = {"trigger_type": "timeout"}
                    break
                if this_timeout is None or this_timeout > time_left:
                    this_timeout = time_left
            if this_timeout is None:
                if state_trigger is None and event_trigger is None:
                    _LOGGER.debug(
                        "trigger %s wait_until no next time - returning with none",
                        ast_ctx.name,
                    )
                    return {"trigger_type": "none"}
                _LOGGER.debug("trigger %s wait_until no timeout", ast_ctx.name)
                notify_type, notify_info = await notify_q.get()
            else:
                try:
                    _LOGGER.debug(
                        "trigger %s wait_until %s secs", ast_ctx.name, this_timeout
                    )
                    notify_type, notify_info = await asyncio.wait_for(
                        notify_q.get(), timeout=this_timeout
                    )
                except asyncio.TimeoutError:
                    ret = {"trigger_type": "time"}
                    break
            if notify_type == "state":
                new_vars = notify_info[0] if notify_info else None
                if state_trig_expr is None or await state_trig_expr.eval(new_vars):
                    ret = notify_info[1] if notify_info else None
                    break
            elif notify_type == "event":
                if event_trig_expr is None or await event_trig_expr.eval(notify_info):
                    ret = notify_info
                    break
            else:
                _LOGGER.error(
                    "trigger %s wait_until got unexpected queue message %s",
                    ast_ctx.name,
                    notify_type,
                )

        if state_trig_ident:
            for name in state_trig_ident:
                ast_ctx.state.notify_del(name, notify_q)
        if event_trigger is not None:
            ast_ctx.event.notify_del(event_trigger[0], notify_q)
        _LOGGER.debug("trigger %s wait_until returning %s", ast_ctx.name, ret)
        return ret

    def parse_date_time(self, date_time_str, day_offset, now):
        """Parse a date time string, returning datetime."""
        year = now.year
        month = now.month
        day = now.day

        dt_str = date_time_str.strip().lower()
        #
        # parse the date
        #
        skip = True
        match0 = re.split(r"^0*(\d+)[-/]0*(\d+)(?:[-/]0*(\d+))?", dt_str)
        match1 = re.split(r"^(\w+).*", dt_str)
        if len(match0) == 5:
            year, month, day = int(match0[1]), int(match0[2]), int(match0[3])
            day_offset = 0  # explicit date means no offset
        elif len(match0) == 4:
            month, day = int(match0[1]), int(match0[2])
            day_offset = 0  # explicit date means no offset
        elif len(match1) == 3:
            if match1[1] in self.dow2int:
                dow = self.dow2int[match1[1]]
                if dow >= (now.isoweekday() % 7):
                    day_offset = dow - (now.isoweekday() % 7)
                else:
                    day_offset = 7 + dow - (now.isoweekday() % 7)
            elif match1[1] == "today":
                day_offset = 0
            elif match1[1] == "tomorrow":
                day_offset = 1
            else:
                skip = False
        else:
            skip = False
        if day_offset != 0:
            now = datetime.datetime(year, month, day) + datetime.timedelta(
                days=day_offset
            )
            year = now.year
            month = now.month
            day = now.day
        else:
            now = datetime.datetime(year, month, day)
        if skip:
            i = dt_str.find(" ")
            if i >= 0:
                dt_str = dt_str[i + 1 :].strip()
            else:
                return now

        #
        # parse the time
        #
        skip = True
        match0 = re.split(
            r"0*(\d+):0*(\d+)(?::0*(\d*\.?\d+(?:[eE][-+]?\d+)?))?", dt_str
        )
        if len(match0) == 5:
            if match0[3] is not None:
                hour, mins, sec = int(match0[1]), int(match0[2]), float(match0[3])
            else:
                hour, mins, sec = int(match0[1]), int(match0[2]), 0
        elif dt_str.startswith("sunrise") or dt_str.startswith("sunset"):
            if dt_str.startswith("sunrise"):
                time_sun = sun.get_astral_event_date(self.hass, SUN_EVENT_SUNRISE)
            else:
                time_sun = sun.get_astral_event_date(self.hass, SUN_EVENT_SUNSET)
            if time_sun is None:
                _LOGGER.warning("'%s' not defined at this latitude", dt_str)
                # return something in the past so it is ignored
                return now - datetime.timedelta(days=100)
            time_sun = dt_util.as_local(time_sun)
            hour, mins, sec = time_sun.hour, time_sun.minute, time_sun.second
            _LOGGER.debug(
                "trigger: got %s = %02d:%02d:%02d (t = %s)",
                dt_str,
                hour,
                mins,
                sec,
                time_sun,
            )
        elif dt_str.startswith("noon"):
            hour, mins, sec = 12, 0, 0
        elif dt_str.startswith("midnight"):
            hour, mins, sec = 0, 0, 0
        else:
            hour, mins, sec = 0, 0, 0
            skip = False
        now = now + datetime.timedelta(seconds=sec + 60 * (mins + 60 * hour))
        if skip:
            i = dt_str.find(" ")
            if i >= 0:
                dt_str = dt_str[i + 1 :].strip()
            else:
                return now
        #
        # parse the offset
        #
        if len(dt_str) > 0 and (dt_str[0] == "+" or dt_str[0] == "-"):
            now = now + datetime.timedelta(seconds=parse_time_offset(dt_str))
        return now

    def timer_active_check(self, time_spec, now):
        """Check if the given time matches the time specification."""
        pos_check = False
        pos_cnt = 0
        neg_check = True

        for entry in time_spec if isinstance(time_spec, list) else [time_spec]:
            this_match = False
            neg = False
            active_str = entry.strip()
            if active_str.startswith("not"):
                neg = True
                active_str = active_str[3:].strip()
            else:
                pos_cnt = pos_cnt + 1
            match0 = re.split(
                r"cron\((\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\)", active_str
            )
            match1 = re.split(r"range\(([^,]*),(.*)\)", active_str)
            if len(match0) == 7:
                cron = match0[1:6]
                check = [now.minute, now.hour, now.day, now.month, now.isoweekday() % 7]
                this_match = True
                for fld in range(5):
                    if check[fld] != cron_ge(cron, fld, check[fld]):
                        this_match = False
                        break
            elif len(match1) == 4:
                start = self.parse_date_time(match1[1].strip(), 0, now)
                end = self.parse_date_time(match1[2].strip(), 0, start)
                if start < end:
                    if start <= now <= end:
                        this_match = True
                else:
                    if start <= now or now <= end:
                        this_match = True
            else:
                this_match = False

            if neg:
                neg_check = neg_check and not this_match
            else:
                pos_check = pos_check or this_match
        #
        # An empty spec, or only neg specs, matches True
        #
        if pos_cnt == 0:
            pos_check = True
        return pos_check and neg_check

    def timer_trigger_next(self, time_spec, now):
        """Return the next trigger time based on the given time and time specification."""
        next_time = None
        if not isinstance(time_spec, list):
            time_spec = [time_spec]
        for spec in time_spec:  # pylint: disable=too-many-nested-blocks
            match0 = re.split(r"cron\((\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\)", spec)
            match1 = re.split(r"once\((.*)\)", spec)
            match2 = re.split(r"period\(([^,]*),([^,]*)(?:,([^,]*))?\)", spec)
            if len(match0) == 7:
                cron = match0[1:6]
                year_next = now.year
                min_next = cron_ge(cron, 0, now.minute)
                mon_next = cron_ge(cron, 3, now.month)  # 1-12
                mday_next = cron_ge(cron, 2, now.day)  # 1-31
                wday_next = cron_ge(cron, 4, now.isoweekday() % 7)  # 0-6
                today = True
                if (
                    (cron[2] == "*" and (now.isoweekday() % 7) != wday_next)
                    or (cron[4] == "*" and now.day != mday_next)
                    or (now.day != mday_next and (now.isoweekday() % 7) != wday_next)
                    or (now.month != mon_next)
                ):
                    today = False
                min_next0 = now.minute + 1
                if (now.hour + 1) <= cron_ge(cron, 1, now.hour):
                    min_next0 = 0
                min_next = cron_ge(cron, 0, min_next0 % 60)

                carry = min_next < min_next0
                hr_next0 = now.hour
                if carry:
                    hr_next0 = hr_next0 + 1
                hr_next = cron_ge(cron, 1, hr_next0 % 24)
                carry = hr_next < hr_next0

                if carry or not today:
                    # this event occurs after today

                    min_next = cron_ge(cron, 0, 0)
                    hr_next = cron_ge(cron, 1, 0)

                    #
                    # calculate the date of the next occurrence of this event, which
                    # will be on a different day than the current
                    #

                    # check monthly day specification
                    d1_next = now.day + 1
                    day1 = cron_ge(
                        cron, 2, (d1_next - 1) % days_in_mon(now.month, now.year) + 1
                    )
                    carry1 = day1 < d1_next

                    # check weekly day specification
                    wday_next2 = (now.isoweekday() % 7) + 1
                    wday_next = cron_ge(cron, 4, wday_next2 % 7)
                    if wday_next < wday_next2:
                        days_ahead = 7 - wday_next2 + wday_next
                    else:
                        days_ahead = wday_next - wday_next2
                    day2 = (d1_next + days_ahead - 1) % days_in_mon(
                        now.month, now.year
                    ) + 1
                    carry2 = day2 < d1_next

                    #
                    # based on their respective specifications, day1, and day2 give
                    # the day of the month for the next occurrence of this event.
                    #
                    if cron[2] == "*" and cron[4] != "*":
                        day1 = day2
                        carry1 = carry2
                    if cron[2] != "*" and cron[4] == "*":
                        day2 = day1
                        carry2 = carry1

                    if (carry1 and carry2) or (now.month != mon_next):
                        # event does not occur in this month
                        if now.month == 12:
                            mon_next = cron_ge(cron, 3, 1)
                            year_next = year_next + 1
                        else:
                            mon_next = cron_ge(cron, 3, now.month + 1)
                        # recompute day1 and day2
                        day1 = cron_ge(cron, 2, 1)
                        days_btwn = (
                            days_between(
                                now.month, now.day, now.year, mon_next, 1, year_next
                            )
                            + 1
                        )
                        wd_next = ((now.isoweekday() % 7) + days_btwn) % 7
                        # wd_next is the day of the week of the first of month mon
                        wday_next = cron_ge(cron, 4, wd_next)
                        if wday_next < wd_next:
                            day2 = 1 + 7 - wd_next + wday_next
                        else:
                            day2 = 1 + wday_next - wd_next
                        if cron[2] != "*" and cron[4] == "*":
                            day2 = day1
                        if cron[2] == "*" and cron[4] != "*":
                            day1 = day2
                        if day1 < day2:
                            mday_next = day1
                        else:
                            mday_next = day2
                    else:
                        # event occurs in this month
                        mon_next = now.month
                        if not carry1 and not carry2:
                            if day1 < day2:
                                mday_next = day1
                            else:
                                mday_next = day2
                        elif not carry1:
                            mday_next = day1
                        else:
                            mday_next = day2

                    #
                    # now that we have the min, hr, day, mon, yr of the next event,
                    # figure out what time that turns out to be.
                    #
                    this_t = datetime.datetime(
                        year_next, mon_next, mday_next, hr_next, min_next, 0
                    )
                    if now < this_t and (next_time is None or this_t < next_time):
                        next_time = this_t
                else:
                    # this event occurs today
                    secs = (
                        3600 * (hr_next - now.hour)
                        + 60 * (min_next - now.minute)
                        - now.second
                        - 1e-6 * now.microsecond
                    )
                    this_t = now + datetime.timedelta(seconds=secs)
                    if now < this_t and (next_time is None or this_t < next_time):
                        next_time = this_t

            elif len(match1) == 3:
                this_t = self.parse_date_time(match1[1].strip(), 0, now)
                if this_t <= now:
                    #
                    # Try tomorrow (won't make a difference if spec has full date)
                    #
                    this_t = self.parse_date_time(match1[1].strip(), 1, now)
                if now < this_t and (next_time is None or this_t < next_time):
                    next_time = this_t

            elif len(match2) == 5:
                start = self.parse_date_time(match2[1].strip(), 0, now)
                if now < start and (next_time is None or start < next_time):
                    next_time = start
                period = parse_time_offset(match2[2].strip())
                if now >= start and period > 0:
                    secs = period * (
                        1.0 + math.floor((now - start).total_seconds() / period)
                    )
                    this_t = start + datetime.timedelta(seconds=secs)
                    if match2[3] is None:
                        if now < this_t and (next_time is None or this_t < next_time):
                            next_time = this_t
                    else:
                        end = self.parse_date_time(match2[3].strip(), 0, now)
                        if end < start:
                            #
                            # end might be a time tomorrow
                            #
                            end = self.parse_date_time(match2[3].strip(), 1, now)
                        if now < this_t <= end and (
                            next_time is None or this_t < next_time
                        ):
                            next_time = this_t
                        if next_time is None or now >= end:
                            #
                            # Try tomorrow's start (won't make a difference if spec has
                            # full date)
                            #
                            start = self.parse_date_time(match2[3].strip(), 1, now)
                            if now < start and (next_time is None or start < next_time):
                                next_time = start
            else:
                _LOGGER.warning("Can't parse %s in time_trigger check", spec)
        return next_time


class TrigInfo:
    """Class for all trigger-decorated functions."""

    def __init__(
        self,
        name,
        trig_cfg,
        event_func=None,
        state_func=None,
        handler_func=None,
        trig_time=None,
    ):
        """Create a new TrigInfo."""
        self.name = name
        self.task = None
        self.trig_cfg = trig_cfg
        self.state_trigger = trig_cfg.get("state_trigger", None)
        self.time_trigger = trig_cfg.get("time_trigger", None)
        self.event_trigger = trig_cfg.get("event_trigger", None)
        self.state_active = trig_cfg.get("state_active", None)
        self.time_active = trig_cfg.get("time_active", None)
        self.action = trig_cfg.get("action")
        self.action_ast_ctx = trig_cfg.get("action_ast_ctx")
        self.global_sym_table = trig_cfg.get("global_sym_table", {})
        self.notify_q = asyncio.Queue(0)
        self.active_expr = None
        self.state_trig_expr = None
        self.state_trig_ident = None
        self.event_trig_expr = None
        self.have_trigger = False
        self.event = event_func
        self.state = state_func
        self.handler = handler_func
        self.trig_time = trig_time

        _LOGGER.debug("trigger %s event_trigger = %s", self.name, self.event_trigger)

        if self.state_active is not None:
            self.active_expr = AstEval(
                f"trigger {self.name} state_active",
                self.global_sym_table,
                state_func=self.state,
                event_func=self.event,
                handler_func=self.handler,
            )
            self.handler.install_ast_funcs(self.active_expr)
            self.active_expr.parse(self.state_active)

        if self.time_trigger is not None:
            self.have_trigger = True

        if self.state_trigger is not None:
            self.state_trig_expr = AstEval(
                f"trigger {self.name} state_trigger",
                self.global_sym_table,
                state_func=self.state,
                event_func=self.event,
                handler_func=self.handler,
            )
            self.handler.install_ast_funcs(self.state_trig_expr)
            self.state_trig_expr.parse(self.state_trigger)
            self.state_trig_ident = self.state_trig_expr.ast_get_names()
            _LOGGER.debug(
                "trigger %s: watching vars %s", self.name, self.state_trig_ident
            )
            if len(self.state_trig_ident) > 0:
                self.state.notify_add(self.state_trig_ident, self.notify_q)
            self.have_trigger = True

        if self.event_trigger is not None:
            _LOGGER.debug(
                "trigger %s adding event_trigger %s", self.name, self.event_trigger[0]
            )
            self.event.notify_add(self.event_trigger[0], self.notify_q)
            if len(self.event_trigger) == 2:
                self.event_trig_expr = AstEval(
                    f"trigger {self.name} event_trigger",
                    self.global_sym_table,
                    state_func=self.state,
                    event_func=self.event,
                    handler_func=self.handler,
                )
                self.handler.install_ast_funcs(self.event_trig_expr)
                self.event_trig_expr.parse(self.event_trigger[1])
            self.have_trigger = True

    async def stop(self):
        """Stop this trigger task."""

        if self.task:
            if self.state_trig_ident:
                self.state.notify_del(self.state_trig_ident, self.notify_q)
            if self.event_trigger is not None:
                self.event.notify_del(self.event_trigger[0], self.notify_q)
            if self.task:
                try:
                    self.task.cancel()
                    await self.task
                except asyncio.CancelledError:
                    pass
            self.task = None
        _LOGGER.debug("trigger %s is stopped", self.name)

    def start(self):
        """Start this trigger task."""
        self.task = self.handler.create_task(self.trigger_watch())
        _LOGGER.debug("trigger %s is active", self.name)

    async def trigger_watch(self):
        """Task that runs for each trigger, waiting for the next trigger and calling the function."""

        while 1:
            try:
                timeout = None
                notify_info = None
                notify_type = None
                if self.time_trigger:
                    now = dt_now()
                    time_next = self.trig_time.timer_trigger_next(
                        self.time_trigger, now
                    )
                    _LOGGER.debug(
                        "trigger %s time_next = %s, now = %s", self.name, time_next, now
                    )
                    if time_next is not None:
                        timeout = (time_next - now).total_seconds()
                if timeout is None and self.have_trigger:
                    _LOGGER.debug(
                        "trigger %s waiting for state change or event", self.name
                    )
                    notify_type, notify_info = await self.notify_q.get()
                elif timeout is not None:
                    try:
                        _LOGGER.debug(
                            "trigger %s waiting for %s secs", self.name, timeout
                        )
                        notify_type, notify_info = await asyncio.wait_for(
                            self.notify_q.get(), timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        notify_info = {"trigger_type": "time"}
                        if (
                            (not self.active_expr or await self.active_expr.eval())
                            and (
                                not self.time_active
                                or self.trig_time.timer_active_check(
                                    self.time_active, dt_now()
                                )
                            )
                            and self.action
                        ):
                            _LOGGER.debug(
                                "trigger %s got time_trigger, running action", self.name
                            )
                            self.handler.create_task(
                                self.action.call(
                                    self.action_ast_ctx, kwargs=notify_info
                                )
                            )
                        else:
                            _LOGGER.debug(
                                "trigger %s got time_trigger, but not active", self.name
                            )
                        continue
                if notify_type == "state" or notify_type is None:
                    if notify_info:
                        new_vars, func_args = notify_info
                    else:
                        new_vars, func_args = {}, {}
                    if (
                        (
                            self.state_trig_expr is None
                            or await self.state_trig_expr.eval(new_vars)
                        )
                        and (
                            self.active_expr is None
                            or await self.active_expr.eval(new_vars)
                        )
                        and (
                            self.time_active is None
                            or self.trig_time.timer_active_check(
                                self.time_active, dt_now()
                            )
                        )
                        and self.action
                    ):
                        _LOGGER.debug(
                            "trigger %s state_trig_expr = %s based on %s",
                            self.name,
                            await self.state_trig_expr.eval(new_vars)
                            if self.state_trig_expr
                            else None,
                            new_vars,
                        )
                        _LOGGER.debug(
                            "trigger %s got state_trig_expr, running action (kwargs = %s)",
                            self.name,
                            func_args,
                        )
                        self.handler.create_task(
                            self.action.call(self.action_ast_ctx, kwargs=func_args)
                        )
                    else:
                        _LOGGER.debug(
                            "trigger %s got state_trig_expr, but not active", self.name
                        )
                        # _LOGGER.debug(f'state_trig_expr = {await self.state_trig_expr.eval(new_vars) if self.state_trig_expr else None}')
                        # _LOGGER.debug(f'timerActive = {self.trig_time.timer_active_check(self.time_active, dt_now())
                        #                                                       if self.time_active else None}')
                elif notify_type == "event":
                    if (
                        (
                            self.event_trig_expr is None
                            or await self.event_trig_expr.eval(notify_info)
                        )
                        and (
                            self.active_expr is None
                            or await self.active_expr.eval(notify_info)
                        )
                        and (
                            self.time_active is None
                            or self.trig_time.timer_active_check(
                                self.time_active, dt_now()
                            )
                        )
                        and self.action
                    ):
                        _LOGGER.debug(
                            "trigger %s got event_trig_expr, running action (kwargs = %s)",
                            self.name,
                            notify_info,
                        )
                        self.handler.create_task(
                            self.action.call(self.action_ast_ctx, kwargs=notify_info)
                        )
                    else:
                        _LOGGER.debug(
                            "trigger %s got event_trig_expr, but not active", self.name
                        )
                elif notify_type is not None:
                    _LOGGER.error(
                        "trigger %s got unexpected queue message %s",
                        self.name,
                        notify_type,
                    )

                #
                # if there is no time, event or state trigger, then quit
                # (empty triggers mean run the function once at startup)
                #
                if (
                    self.state_trigger is None
                    and self.time_trigger is None
                    and self.event_trigger is None
                ):
                    _LOGGER.debug("trigger %s returning", self.name)
                    return
            except asyncio.CancelledError:  # pylint: disable=try-except-raise
                raise
            except Exception:  # pylint: disable=broad-except
                # _LOGGER.error(f"{self.name}: " + traceback.format_exc(-1))
                if self.state_trig_ident:
                    self.state.notify_del(self.state_trig_ident, self.notify_q)
                if self.event_trigger is not None:
                    self.event.notify_del(self.event_trigger[0], self.notify_q)
                return
