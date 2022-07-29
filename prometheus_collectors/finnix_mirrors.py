# SPDX-FileComment: prometheus-finnix-mirrors
# SPDX-FileCopyrightText: Copyright (C) 2022 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

import sys

import dateutil.parser
from prometheus_client import Counter

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "finnix_mirrors"
    needs_requests = True

    def collect_metrics(self):
        r = self.r_session.get("https://mirrors.finnix.org/mirrors.json")
        r.raise_for_status()
        j = r.json()
        for mirror_name, mirror in j["mirrors"].items():
            for mirror_url in mirror["urls"]:
                self.collect_mirror_url(mirror, mirror_name, mirror_url, r)

    def collect_mirror_url(self, mirror, mirror_name, mirror_url, r):
        labels = {"mirror": mirror_name, "protocol": mirror_url["protocol"]}
        self.metric(
            "collection_time_seconds", labels, "Time mirror data was collected"
        ).set(dateutil.parser.parse(r.headers["Date"]).timestamp())
        self.metric(
            "check_success", labels, "Whether the last check was a success"
        ).set(int(mirror_url["check_success"]))
        for s, d, h in [
            (
                "date_last_check",
                "last_check_time_seconds",
                "Time mirror was last checked",
            ),
            (
                "date_last_success",
                "last_success_time_seconds",
                "Time mirror was last successful",
            ),
            ("date_last_trace", "last_trace_time_seconds", "Time of mirror trace file"),
        ]:
            if mirror_url.get(s):
                self.metric(d, labels, h).set(
                    dateutil.parser.parse(mirror_url[s]).timestamp()
                )
        self.metric(
            "collections_total",
            labels,
            "Total collections processed",
            data_type=Counter,
        ).inc()


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
