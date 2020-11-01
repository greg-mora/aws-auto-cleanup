import sys
import datetime

import boto3

from src.helper import Helper


class GlueCleanup:
    def __init__(self, logging, whitelist, settings, execution_log, region):
        self.logging = logging
        self.whitelist = whitelist
        self.settings = settings
        self.execution_log = execution_log
        self.region = region

        self._client_glue = None
        self._dry_run = self.settings.get("general", {}).get("dry_run", True)

    @property
    def client_glue(self):
        if not self._client_glue:
            self._client_glue = boto3.client("glue", region_name=self.region)
        return self._client_glue

    def run(self):
        self.dev_endpoints()

    def dev_endpoints(self):
        """
        Deletes Glue Dev Endpoints.
        """

        self.logging.debug("Started cleanup of Glue Dev Endpoints.")

        clean = (
            self.settings.get("services", {})
            .get("glue", {})
            .get("dev_endpoint", {})
            .get("clean", False)
        )
        if clean:
            try:
                resources = self.client_glue.get_dev_endpoints().get("DevEndpoints")
            except:
                self.logging.error("Could not list all Glue Dev Endpoints.")
                self.logging.error(sys.exc_info()[1])
                return False

            ttl_days = (
                self.settings.get("services", {})
                .get("glue", {})
                .get("dev_endpoint", {})
                .get("ttl", 7)
            )

            for resource in resources:
                resource_id = resource.get("EndpointName")
                resource_date = resource.get("LastModifiedTimestamp")
                resource_action = None

                if resource_id not in self.whitelist.get("glue", {}).get(
                    "dev_endpoint", []
                ):
                    delta = Helper.get_day_delta(resource_date)

                    if delta.days > ttl_days:
                        try:
                            if not self._dry_run:
                                self.client_glue.delete_dev_endpoint(
                                    EndpointName=resource_id
                                )
                        except:
                            self.logging.error(
                                f"Could not delete Glue Dev Endpoint '{resource_id}'."
                            )
                            self.logging.error(sys.exc_info()[1])
                            resource_action = "ERROR"
                        else:
                            self.logging.info(
                                f"Glue Dev Endpoint '{resource_id}' was last modified {delta.days} days ago "
                                "and has been deleted."
                            )
                            resource_action = "DELETE"
                    else:
                        self.logging.debug(
                            f"Glue Dev Endpoint '{resource_id}' was last modified {delta.days} days ago "
                            "(less than TTL setting) and has not been deleted."
                        )
                        resource_action = "SKIP - TTL"
                else:
                    self.logging.debug(
                        f"Glue Dev Endpoint '{resource_id}' has been whitelisted and has not been deleted."
                    )
                    resource_action = "SKIP - WHITELIST"

                self.execution_log.get("AWS").setdefault(self.region, {}).setdefault(
                    "glue", {}
                ).setdefault("dev_endpoint", []).append(
                    {
                        "id": resource_id,
                        "action": resource_action,
                        "timestamp": datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }
                )

            self.logging.debug("Finished cleanup of Glue Dev Endpoints.")
            return True
        else:
            self.logging.info("Skipping cleanup of Glue Dev Endpoints.")
            return True
