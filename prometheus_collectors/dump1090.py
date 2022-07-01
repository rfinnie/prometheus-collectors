# SPDX-FileComment: prometheus-dump1090
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample dump1090.yaml:
#
# stations:
# - name: piaware
#   url: http://piaware.example.lan/skyaware/data/aircraft.json

import platform
import sys

from prometheus_client import Counter, Gauge
import requests

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "dump1090"

    def setup(self):
        self.metrics = {}
        # < 58 and < 60 mirrors the logic of the PiAware 5.0 JS UI
        self.seen_fresh_time = self.config.get("seen_fresh_time", 58)
        self.seen_pos_fresh_time = self.config.get("seen_pos_fresh_time", 60)
        label_names = ["station"]

        defs = [
            ("reports_total", Counter, "Total reports received"),
            ("station_time_seconds", Gauge, "Station collection time"),
            ("messages_received", Gauge, "Number of raw messages received"),
            (
                "airborne_aircraft_total",
                Gauge,
                "Total number of current airborne aircraft seen",
            ),
            (
                "airborne_aircraft_positions",
                Gauge,
                "Number of current airborne aircraft seen with positions",
            ),
            (
                "airborne_aircraft_mlat",
                Gauge,
                "Number of current airborne aircraft seen with multilateration",
            ),
            (
                "airborne_aircraft_tisb",
                Gauge,
                "Number of current airborne aircraft seen with TIS-B information",
            ),
            (
                "airborne_aircraft_squawk",
                Gauge,
                "Number of current airborne aircraft seen squawking",
            ),
            (
                "airborne_aircraft_ground",
                Gauge,
                "Number of current aircraft reported on ground",
            ),
            (
                "airborne_aircraft_messages",
                Gauge,
                "Number of messages received by currently seen airborne aircraft",
            ),
        ]

        for k, t, h in defs:
            self.metrics[k] = t(
                "{}_{}".format(self.prefix, k), h, label_names, registry=self.registry
            )

        if "stations" not in self.config:
            self.config["stations"] = [
                {
                    "name": platform.node(),
                    "url": "http://127.0.0.1/skyaware/data/aircraft.json",
                }
            ]

    def collect_metrics(self):
        for station in self.config["stations"]:
            self.collect_station(station)

    def collect_station(self, station):
        r = requests.get(station["url"])
        r.raise_for_status()
        j = r.json()
        aircraft = [x for x in j["aircraft"] if x["seen"] < self.seen_fresh_time]

        labels = [station["name"]]
        vals = [
            ("messages_received", j["messages"]),
            ("airborne_aircraft_total", len(aircraft)),
            (
                "airborne_aircraft_positions",
                len(
                    [
                        x
                        for x in aircraft
                        if "lat" in x
                        and "seen_pos" in x
                        and x["seen_pos"] < self.seen_pos_fresh_time
                    ]
                ),
            ),
            ("airborne_aircraft_mlat", len([x for x in aircraft if x.get("mlat")])),
            ("airborne_aircraft_tisb", len([x for x in aircraft if x.get("tisb")])),
            ("airborne_aircraft_squawk", len([x for x in aircraft if x.get("squawk")])),
            (
                "airborne_aircraft_ground",
                len([x for x in aircraft if x.get("alt_baro") == "ground"]),
            ),
            (
                "airborne_aircraft_messages",
                sum([x["messages"] for x in aircraft if "messages" in x]),
            ),
            ("station_time_seconds", j["now"]),
        ]
        for k, v in vals:
            self.metrics[k].labels(*labels).set(v)
        self.metrics["reports_total"].labels(*labels).inc()


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
