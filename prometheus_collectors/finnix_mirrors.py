# SPDX-FileComment: prometheus-finnix-mirrors
# SPDX-FileCopyrightText: Copyright (C) 2022 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

import sys

import dateutil.parser
from prometheus_client import Counter, Gauge
import requests

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "finnix_mirrors"

    def setup(self):
        self.metrics = {}
        label_names = ["mirror", "protocol"]

        defs = [
            ("collections_total", Counter, "Total collections processed"),
            ("collection_time_seconds", Gauge, "Time mirror data was collected"),
            ("last_check_time_seconds", Gauge, "Time mirror was last checked"),
            ("last_success_time_seconds", Gauge, "Time mirror was last successful"),
            ("last_trace_time_seconds", Gauge, "Time of mirror trace file"),
            ("check_success", Gauge, "Whether the last check was a success"),
        ]

        for k, t, h in defs:
            self.metrics[k] = t(
                "{}_{}".format(self.prefix, k), h, label_names, registry=self.registry
            )

    def collect_metrics(self):
        r = requests.get("https://mirrors.finnix.org/mirrors.json")
        r.raise_for_status()
        j = r.json()
        for mirror_name, mirror in j["mirrors"].items():
            for mirror_url in mirror["urls"]:
                self.collect_mirror_url(mirror, mirror_name, mirror_url, r)

    def collect_mirror_url(self, mirror, mirror_name, mirror_url, r):
        labels = [mirror_name, mirror_url["protocol"]]
        vals = [
            (
                "collection_time_seconds",
                dateutil.parser.parse(r.headers["Date"]).timestamp(),
            ),
            ("check_success", int(mirror_url["check_success"])),
        ]
        for s, d in [
            ("date_last_check", "last_check_time_seconds"),
            ("date_last_success", "last_success_time_seconds"),
            ("date_last_trace", "last_trace_time_seconds"),
        ]:
            if mirror_url.get(s):
                vals.append((d, dateutil.parser.parse(mirror_url[s]).timestamp()))
        for k, v in vals:
            self.metrics[k].labels(*labels).set(v)
        self.metrics["collections_total"].labels(*labels).inc()


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
