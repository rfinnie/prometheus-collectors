# SPDX-FileComment: finnix-collector-mirrors
# SPDX-FileCopyrightText: Copyright (C) 2022 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

import sys

import dateutil.parser

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "finnix_mirrors"
    needs_requests = True

    def setup(self):
        self.create_instrument(
            "gauge",
            "collection.time",
            unit="seconds",
            description="Time mirror data was collected",
        )
        self.create_instrument(
            "gauge", "check.success", description="Whether the last check was a success"
        )
        self.create_instrument(
            "gauge",
            "last.check.time",
            unit="seconds",
            description="Time mirror was last checked",
        )
        self.create_instrument(
            "gauge",
            "last.success.time",
            unit="seconds",
            description="Time mirror was last successful",
        )
        self.create_instrument(
            "gauge",
            "last.trace.time",
            unit="seconds",
            description="Time of mirror trace file",
        )
        self.create_instrument(
            "counter", "collections", description="Total collections processed"
        )

    def collect_metrics(self):
        r = self.r_session.get("https://mirrors.finnix.org/mirrors.json")
        r.raise_for_status()
        j = r.json()
        for mirror_name, mirror in j["mirrors"].items():
            for mirror_url in mirror["urls"]:
                self.collect_mirror_url(mirror, mirror_name, mirror_url, r)

    def collect_mirror_url(self, mirror, mirror_name, mirror_url, r):
        labels = {"mirror": mirror_name, "protocol": mirror_url["protocol"]}
        self.instruments["collection.time"].set(
            dateutil.parser.parse(r.headers["Date"]).timestamp(), labels
        )
        self.instruments["check.success"].set(int(mirror_url["check_success"]), labels)
        for s, d in [
            ("date_last_check", "last.check.time"),
            ("date_last_success", "last.success.time"),
            ("date_last_trace", "last.trace.time"),
        ]:
            if mirror_url.get(s):
                self.instruments[d].set(
                    dateutil.parser.parse(mirror_url[s]).timestamp(), labels
                )
        self.instruments["collections"].add(1, labels)


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
