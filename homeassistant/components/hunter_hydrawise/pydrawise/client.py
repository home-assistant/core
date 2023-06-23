"""Client library for interacting with Hydrawise's cloud API."""

from datetime import datetime
from functools import cache
import logging

from apischema.graphql import graphql_schema
from gql import Client
from gql.dsl import DSLField, DSLMutation, DSLQuery, DSLSchema, DSLSelectable, dsl_gql
from gql.transport.aiohttp import AIOHTTPTransport, log as gql_log
from graphql import GraphQLSchema

from .auth import Auth
from .exceptions import MutationError
from .schema import (
    Controller,
    DateTime,
    Mutation,
    Query,
    StatusCodeAndSummary,
    User,
    Zone,
    ZoneSuspension,
)
from .schema_utils import deserialize, get_selectors

# GQL is quite chatty in logs by default.
gql_log.setLevel(logging.ERROR)

API_URL = "https://app.hydrawise.com/api/v2/graph"


@cache
def _get_schema() -> GraphQLSchema:
    return graphql_schema(
        query=[getattr(Query, m) for m in Query.__abstractmethods__],
        mutation=[getattr(Mutation, m) for m in Mutation.__abstractmethods__],
    )


class Hydrawise:
    """Client library for interacting with Hydrawise sprinkler controllers.

    Should be instantiated with an Auth object that handles authentication and low-level transport.
    """

    def __init__(self, auth: Auth) -> None:
        """Initialize the client.

        :param auth: Handles authentication and transport.
        """
        self._auth = auth
        self._schema = DSLSchema(_get_schema())

    async def _client(self) -> Client:
        headers = {"Authorization": await self._auth.token()}
        transport = AIOHTTPTransport(url=API_URL, headers=headers)
        return Client(transport=transport, parse_results=True)

    async def _query(self, selector: DSLSelectable) -> dict:
        async with await self._client() as session:
            return await session.execute(dsl_gql(DSLQuery(selector)))

    async def _mutation(self, selector: DSLField) -> None:
        async with await self._client() as session:
            result = await session.execute(dsl_gql(DSLMutation(selector)))
            resp = result[selector.name]
            if isinstance(resp, dict):
                if resp["status"] not in ("OK", "WARNING"):
                    raise MutationError(resp["summary"])
                return
            if not resp:
                # Assume bool response
                raise MutationError

    async def get_user(self) -> User:
        """Retrieve the currently authenticated user.

        :rtype: User
        """
        selector = self._schema.Query.me.select(*get_selectors(self._schema, User))
        result = await self._query(selector)
        return deserialize(User, result["me"])

    async def get_controllers(self) -> list[Controller]:
        """Retrieve all controllers associated with the currently authenticated user.

        :rtype: list[Controller]
        """
        selector = self._schema.Query.me.select(
            self._schema.User.controllers.select(
                *get_selectors(self._schema, Controller)
            ),
        )
        result = await self._query(selector)
        return deserialize(list[Controller], result["me"]["controllers"])

    async def get_controller(self, controller_id: int) -> Controller:
        """Retrieve a single controller by its unique identifier.

        :param controller_id: Unique identifier for the controller to retrieve.
        :rtype: Controller
        """
        selector = self._schema.Query.controller(controllerId=controller_id).select(
            *get_selectors(self._schema, Controller),
        )
        result = await self._query(selector)
        return deserialize(Controller, result["controller"])

    async def get_zones(self, controller: Controller) -> list[Zone]:
        """Retrieve zones associated with the given controller.

        :param controller: Controller whose zones to fetch.
        :rtype: list[Zone]
        """
        selector = self._schema.Query.controller(controllerId=controller.id).select(
            self._schema.Controller.zones.select(*get_selectors(self._schema, Zone)),
        )
        result = await self._query(selector)
        return deserialize(list[Zone], result["controller"]["zones"])

    async def get_zone(self, zone_id: int) -> Zone:
        """Retrieve a zone by its unique identifier.

        :param zone_id: The zone's unique identifier.
        :rtype: Zone
        """
        selector = self._schema.Query.zone(zoneId=zone_id).select(
            *get_selectors(self._schema, Zone)
        )
        result = await self._query(selector)
        return deserialize(Zone, result["zone"])

    async def start_zone(
        self,
        zone: Zone,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
        stack_runs: bool = False,
    ):
        """Start a zone's run cycle.

        :param zone: The zone to start.
        :param mark_run_as_scheduled: Whether to mark the zone as having run as scheduled.
        :param custom_run_duration: Duration (in seconds) to run the zone. If not
            specified (or zero), will run for its default configured time.
        """
        kwargs = {
            "zoneId": zone.id,
            "markRunAsScheduled": mark_run_as_scheduled,
            "stackRuns": stack_runs,
        }
        if custom_run_duration > 0:
            kwargs["customRunDuration"] = custom_run_duration

        selector = self._schema.Mutation.startZone.args(**kwargs).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def stop_zone(self, zone: Zone):
        """Stop a zone.

        :param zone: The zone to stop.
        """
        selector = self._schema.Mutation.stopZone.args(zoneId=zone.id).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def start_all_zones(
        self,
        controller: Controller,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ):
        """Start all zones attached to a controller.

        :param controller: The controller whose zones to start.
        :param mark_run_as_scheduled: Whether to mark the zones as having run as scheduled.
        :param custom_run_duration: Duration (in seconds) to run the zones. If not
            specified (or zero), will run for each zone's default configured time.
        """
        kwargs = {
            "controllerId": controller.id,
            "markRunAsScheduled": mark_run_as_scheduled,
        }
        if custom_run_duration > 0:
            kwargs["customRunDuration"] = custom_run_duration

        selector = self._schema.Mutation.startAllZones.args(**kwargs).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def stop_all_zones(self, controller: Controller):
        """Stop all zones attached to a controller.

        :param controller: The controller whose zones to stop.
        """
        selector = self._schema.Mutation.stopAllZones.args(
            controllerId=controller.id
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def suspend_zone(self, zone: Zone, until: datetime):
        """Suspend a zone's schedule.

        :param zone: The zone to suspend.
        :param until: When the suspension should end.
        """
        selector = self._schema.Mutation.suspendZone.args(
            zoneId=zone.id,
            until=DateTime.to_json(until).value,
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def resume_zone(self, zone: Zone):
        """Resume a zone's schedule.

        :param zone: The zone whose schedule to resume.
        """
        selector = self._schema.Mutation.resumeZone.args(zoneId=zone.id).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def suspend_all_zones(self, controller: Controller, until: datetime):
        """Suspend the schedule of all zones attached to a given controller.

        :param controller: The controller whose zones to suspend.
        :param until: When the suspension should end.
        """
        selector = self._schema.Mutation.suspendAllZones.args(
            controllerId=controller.id,
            until=DateTime.to_json(until).value,
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def resume_all_zones(self, controller: Controller):
        """Resume the schedule of all zones attached to the given controller.

        :param controller: The controller whose zones to resume.
        """
        selector = self._schema.Mutation.resumeAllZones.args(
            controllerId=controller.id
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def delete_zone_suspension(self, suspension: ZoneSuspension):
        """Remove a specific zone suspension.

        Useful when there are multiple suspensions for a zone in effect.

        :param suspension: The suspension to delete.
        """
        selector = self._schema.Mutation.deleteZoneSuspension.args(
            id=suspension.id
        ).select()
        await self._mutation(selector)
