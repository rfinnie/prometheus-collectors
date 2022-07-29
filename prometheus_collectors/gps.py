# SPDX-FileComment: prometheus-gps
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample gps.yaml:
#
# host: 127.0.0.1
# port: 2947

import json
import socket
import sys
import time

import dateutil.parser
from prometheus_client import Counter

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "gps"
    gpsd_host = "127.0.0.1"
    gpsd_port = 2947
    sock = None

    def setup(self):
        self.gpsd_host = self.config.get("gpsd_host", "127.0.0.1")
        self.gpsd_port = self.config.get("gpsd_port", 2947)

        self.metrics_defs = {
            "PPS": {
                "_clock": (
                    "pps_clock_seconds",
                    "System wall clock, seconds since epoch",
                ),
                "_real": ("pps_real_seconds", "PPS source clock, seconds since epoch"),
                "precision": (
                    "pps_precision_gps",
                    "NTP style estimate of PPS precision",
                ),
            },
            "SKY": {
                "_unused_satellites": (
                    "sky_unused_satellites",
                    "Satellites currently not being used",
                ),
                "_used_satellites": (
                    "sky_used_satellites",
                    "Satellites currently being used",
                ),
                "gdop": (
                    "sky_geometric_dop",
                    "Geometric (hyperspherical) dilution of precision (dimensionless)",
                ),
                "hdop": (
                    "sky_horizontal_dop",
                    "Horizontal dilution of precision (dimensionless)",
                ),
                "pdop": (
                    "sky_position_dop",
                    "Position (spherical/3D) dilution of precision (dimensionless)",
                ),
                "tdop": ("sky_time_dop", "Time dilution of precision (dimensionless)"),
                "vdop": (
                    "sky_vertical_dop",
                    "Vertical (altitude) dilution of precision (dimensionless)",
                ),
                "xdop": (
                    "sky_longitudinal_dop",
                    "Longitudinal (X) dilution of precision (dimensionless)",
                ),
                "ydop": (
                    "sky_latitudinal_dop",
                    "Latitudinal (Y) dilution of precision (dimensionless)",
                ),
            },
            "TPV": {
                "_time": ("tpv_time_seconds", "GPS time"),
                "alt": ("tpv_altitude_meters", "Altitude in meters"),
                "climb": ("tpv_climb_mps", "Climb or sink rate, meters per second"),
                "epc": (
                    "tpv_climb_error_mps",
                    "Estimated climb error in meters per second",
                ),
                "eps": (
                    "tpv_speed_error_mps",
                    "Estimated speed error in meters per second",
                ),
                "ept": (
                    "tpv_time_error_seconds",
                    "Estimated timestamp error in seconds",
                ),
                "epv": (
                    "tpv_vertical_error_meters",
                    "Estimated vertical error in meters",
                ),
                "epx": (
                    "tpv_longitude_error_meters",
                    "Longitude error estimate in meters",
                ),
                "epy": (
                    "tpv_latitude_error_meters",
                    "Latitude error estimate in meters",
                ),
                "mode": ("tpv_mode", "NMEA mode"),
                "speed": ("tpv_speed_mps", "Speed over ground, meters per second"),
                "track": (
                    "tpv_course_degrees",
                    "Course over ground, degrees from true north",
                ),
            },
        }
        if self.config.get("collect_position", True):
            self.metrics_defs["TPV"]["lat"] = (
                "tpv_latitude_degrees",
                "Latitude in degrees",
            )
            self.metrics_defs["TPV"]["lon"] = (
                "tpv_longitude_degrees",
                "Longitude in degrees",
            )

    def process_message(self, buf):
        try:
            j = json.loads(buf)
        except Exception:
            return
        if "class" not in j:
            return
        device = j.get("device", "")
        labels = {"device": device}
        self.metric(
            "messages_total",
            {"device": device, "class": j["class"]},
            "Total messages received",
            data_type=Counter,
        ).inc()
        if j["class"] in self.metrics_defs:
            for k, g in self.metrics_defs[j["class"]].items():
                if k not in j:
                    continue
                self.metric(g[0], labels, g[1]).set(j[k])
        if j["class"] == "PPS":
            m = self.metrics_defs["PPS"]["_clock"]
            self.metric(m[0], labels, m[1]).set(
                j["clock_sec"] + (j["clock_nsec"] / 1000000000)
            )
            m = self.metrics_defs["PPS"]["_real"]
            self.metric(m[0], labels, m[1]).set(
                j["real_sec"] + (j["real_nsec"] / 1000000000)
            )
        elif j["class"] == "SKY":
            m = self.metrics_defs["SKY"]["_unused_satellites"]
            self.metric(m[0], labels, m[1]).set(
                len([x["PRN"] for x in j["satellites"] if not x["used"]])
            )
            m = self.metrics_defs["SKY"]["_used_satellites"]
            self.metric(m[0], labels, m[1]).set(
                len([x["PRN"] for x in j["satellites"] if x["used"]])
            )
        elif j["class"] == "TPV" and j.get("time"):
            m = self.metrics_defs["TPV"]["_time"]
            self.metric(m[0], labels, m[1]).set(
                dateutil.parser.parse(j["time"]).timestamp()
            )

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
                    self.logger.exception("Error during gpsd connection")
                self.collection_errors.inc()
                self.sock.close()
                self.sock = None
                time.sleep(1)
                continue
            try:
                with self.collection_duration.time():
                    self.process_message(data)
            except Exception:
                self.logger.exception("Encountered an error during collection")
                self.collection_errors.inc()


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
