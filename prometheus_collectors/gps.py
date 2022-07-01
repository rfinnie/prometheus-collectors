# SPDX-FileComment: prometheus-gps
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample gps.yaml:
#
# host: 127.0.0.1
# port: 2947

import json
import logging
import socket
import sys
import time

import dateutil.parser
from prometheus_client import Gauge, Counter

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "gps"
    gpsd_host = "127.0.0.1"
    gpsd_port = 2947
    sock = None

    def setup(self):
        self.gpsd_host = self.config.get("gpsd_host", "127.0.0.1")
        self.gpsd_port = self.config.get("gpsd_port", 2947)
        self.metrics = {}

        def dev_gauge(name, desc):
            return Gauge(
                "{}_{}".format(self.prefix, name),
                desc,
                ["device"],
                registry=self.registry,
            )

        self.metrics["messages_total"] = Counter(
            "{}_messages_total".format(self.prefix),
            "Total messages received",
            ["class", "device"],
            registry=self.registry,
        )

        self.metrics_defs = {
            "PPS": {
                "_clock": dev_gauge(
                    "pps_clock_seconds", "System wall clock, seconds since epoch"
                ),
                "_real": dev_gauge(
                    "pps_real_seconds", "PPS source clock, seconds since epoch"
                ),
                "precision": dev_gauge(
                    "pps_precision_gps", "NTP style estimate of PPS precision"
                ),
            },
            "SKY": {
                "_unused_satellites": dev_gauge(
                    "sky_unused_satellites", "Satellites currently not being used"
                ),
                "_used_satellites": dev_gauge(
                    "sky_used_satellites", "Satellites currently being used"
                ),
                "gdop": dev_gauge(
                    "sky_geometric_dop",
                    "Geometric (hyperspherical) dilution of precision (dimensionless)",
                ),
                "hdop": dev_gauge(
                    "sky_horizontal_dop",
                    "Horizontal dilution of precision (dimensionless)",
                ),
                "pdop": dev_gauge(
                    "sky_position_dop",
                    "Position (spherical/3D) dilution of precision (dimensionless)",
                ),
                "tdop": dev_gauge(
                    "sky_time_dop", "Time dilution of precision (dimensionless)"
                ),
                "vdop": dev_gauge(
                    "sky_vertical_dop",
                    "Vertical (altitude) dilution of precision (dimensionless)",
                ),
                "xdop": dev_gauge(
                    "sky_longitudinal_dop",
                    "Longitudinal (X) dilution of precision (dimensionless)",
                ),
                "ydop": dev_gauge(
                    "sky_latitudinal_dop",
                    "Latitudinal (Y) dilution of precision (dimensionless)",
                ),
            },
            "TPV": {
                "_time": dev_gauge("tpv_time_seconds", "GPS time"),
                "alt": dev_gauge("tpv_altitude_meters", "Altitude in meters"),
                "climb": dev_gauge(
                    "tpv_climb_mps", "Climb or sink rate, meters per second"
                ),
                "epc": dev_gauge(
                    "tpv_climb_error_mps", "Estimated climb error in meters per second"
                ),
                "eps": dev_gauge(
                    "tpv_speed_error_mps", "Estimated speed error in meters per second"
                ),
                "ept": dev_gauge(
                    "tpv_time_error_seconds", "Estimated timestamp error in seconds"
                ),
                "epv": dev_gauge(
                    "tpv_vertical_error_meters", "Estimated vertical error in meters"
                ),
                "epx": dev_gauge(
                    "tpv_longitude_error_meters", "Longitude error estimate in meters"
                ),
                "epy": dev_gauge(
                    "tpv_latitude_error_meters", "Latitude error estimate in meters"
                ),
                "mode": dev_gauge("tpv_mode", "NMEA mode"),
                "speed": dev_gauge(
                    "tpv_speed_mps", "Speed over ground, meters per second"
                ),
                "track": dev_gauge(
                    "tpv_course_degrees", "Course over ground, degrees from true north"
                ),
            },
        }
        if self.config.get("collect_position", True):
            self.metrics_defs["TPV"]["lat"] = dev_gauge(
                "tpv_latitude_degrees", "Latitude in degrees"
            )
            self.metrics_defs["TPV"]["lon"] = dev_gauge(
                "tpv_longitude_degrees", "Longitude in degrees"
            )

    def process_message(self, buf):
        try:
            j = json.loads(buf)
        except Exception:
            return
        if "class" not in j:
            return
        device = j.get("device", "")
        self.metrics["messages_total"].labels(j["class"], device).inc()
        if j["class"] in self.metrics_defs:
            for k, g in self.metrics_defs[j["class"]].items():
                if k not in j:
                    continue
                g.labels(device).set(j[k])
        if j["class"] == "PPS":
            m = self.metrics_defs["PPS"]
            m["_clock"].labels(device).set(
                j["clock_sec"] + (j["clock_nsec"] / 1000000000)
            )
            m["_real"].labels(device).set(j["real_sec"] + (j["real_nsec"] / 1000000000))
        elif j["class"] == "SKY":
            m = self.metrics_defs["SKY"]
            m["_unused_satellites"].labels(device).set(
                len([x["PRN"] for x in j["satellites"] if not x["used"]])
            )
            m["_used_satellites"].labels(device).set(
                len([x["PRN"] for x in j["satellites"] if x["used"]])
            )
        elif j["class"] == "TPV" and j.get("time"):
            m = self.metrics_defs["TPV"]
            m["_time"].labels(device).set(dateutil.parser.parse(j["time"]).timestamp())

    def collect_metrics(self):
        pass

    def main_loop_connection(self):
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.gpsd_host, self.gpsd_port))
            self.sock.send(b'?WATCH={"enable":true,"json":true};\n')
        data = self.sock.recv(1024)
        if data == b"":
            raise ValueError("gpsd EOF")
        return data

    def main_loop(self):
        if not self.args.http_daemon:
            raise RuntimeError("Only --http-daemon is supported here")

        while True:
            try:
                data = self.main_loop_connection()
            except Exception as e:
                if not isinstance(e, ConnectionRefusedError):
                    # Silently ignore connection refused
                    logging.exception("Error during gpsd connection")
                self.collection_errors.inc()
                self.sock.close()
                self.sock = None
                time.sleep(1)
                continue
            try:
                with self.collection_duration.time():
                    self.process_message(data)
            except Exception:
                logging.exception("Encountered an error during collection")
                self.collection_errors.inc()


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
