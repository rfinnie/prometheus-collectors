# SPDX-FileComment: prometheus-ups
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample ups.yaml:
#
# upses:
# - host: 127.0.0.1
#   port: 3551

import re
import socket
import struct
import sys

import dateutil.parser
import dateutil.tz
from prometheus_client import Counter, Gauge

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "ups"
    matches = {
        "LINEV": ("line", "volts"),
        "LOADPCT": ("load", "percent"),
        "BCHARGE": ("battery_charge", "percent"),
        "TIMELEFT": ("time_left", "seconds"),
        "MBATTCHG": ("minimum_battery_charge", "percent"),
        "MINTIMEL": ("minimum_time_left", "seconds"),
        "MAXTIME": ("maximum_time", "seconds"),
        "LOTRANS": ("low_transfer", "volts"),
        "HITRANS": ("high_transfer", "volts"),
        "ALARMDEL": ("alarm_delay", "seconds"),
        "BATTV": ("battery", "volts"),
        "NUMXFERS": ("transfer_count", None),
        "TONBATT": ("on_battery", "seconds"),
        "CUMONBATT": ("cumulative_on_battery", "seconds"),
        "NOMINV": ("nominal_input", "volts"),
        "NOMBATTV": ("nominal_battery", "volts"),
        "NOMPOWER": ("nominal_power", "watts"),
    }

    def setup(self):
        label_names = ["model", "name", "serial"]
        self.metrics = {}
        self.metrics["device_time_seconds"] = Gauge(
            "{}_device_time_seconds".format(self.prefix),
            "UPS device check-in time",
            label_names,
            registry=self.registry,
        )
        self.metrics["reports_total"] = Counter(
            "{}_reports_total".format(self.prefix),
            "Total reports received",
            label_names,
            registry=self.registry,
        )

        for status_key in self.matches:
            metric_base, metric_suffix = self.matches[status_key]
            metric_name = metric_base
            if metric_suffix:
                metric_name = "{}_{}".format(metric_name, metric_suffix)
            self.metrics[metric_name] = Gauge(
                "{}_{}".format(self.prefix, metric_name),
                "UPS {}".format(status_key),
                label_names,
                registry=self.registry,
            )

        if "upses" not in self.config:
            self.config["upses"] = [{"host": "127.0.0.1", "port": 3551}]

    def get_apc(self, ups):
        apc_data = b""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ups["host"], ups["port"]))

        sock.send(struct.pack("!H", 6))
        sock.send(b"status")
        while True:
            data = sock.recv(2)
            if data == b"":
                sock.close()
                sock = None
                apc_data = b""
                break
            line_len = struct.unpack("!H", data)[0]
            if line_len == 0:
                break
            data = sock.recv(line_len)
            if data == b"":
                sock.close()
                sock = None
                apc_data = b""
                break
            apc_data += data
        return apc_data.decode("UTF-8")

    def collect_metrics(self):
        for ups in self.config["upses"]:
            self.collect_ups(ups)

    def collect_ups(self, ups):
        if "port" not in ups:
            ups["port"] = 3551

        out = {}

        text = self.get_apc(ups)
        if not text:
            return

        re_line = re.compile(r"^([A-Z ]+?) *: (.*?) *$", re.M)
        kv = {k: v for (k, v) in re_line.findall(text)}
        for k, v in kv.items():
            if k not in self.matches:
                continue
            (m_name, m_suffix) = self.matches[k]
            if k == "ALARMDEL" and v == "No alarm":
                v = "0 Seconds"
            if m_suffix:
                v_suffix = v.split(" ")[-1].lower()
                v = " ".join(v.split(" ")[0:-1])
                if m_suffix == "seconds":
                    if v_suffix == "hours":
                        v = str(float(v) * 3600)
                        v_suffix = "seconds"
                    elif v_suffix == "minutes":
                        v = str(float(v) * 60)
                        v_suffix = "seconds"
                if v_suffix != m_suffix:
                    print("Unexpected: {} {} {}".format(k, v_suffix, m_suffix))
                    continue
            fullname = m_name
            if m_suffix:
                fullname = "{}_{}".format(fullname, m_suffix)
            out[k] = v

        labels = [kv["MODEL"], kv["UPSNAME"], kv["SERIALNO"]]
        for k, v in out.items():
            m_name, m_suffix = self.matches[k]
            fullname = m_name
            if m_suffix:
                fullname = "{}_{}".format(fullname, m_suffix)
            self.metrics[fullname].labels(*labels).set(v)
        apc_date = dateutil.parser.parse(kv["DATE"])
        if apc_date.tzinfo is None:
            apc_date = apc_date.astimezone(dateutil.tz.tzlocal())
        self.metrics["device_time_seconds"].labels(*labels).set(
            float(apc_date.strftime("%s"))
        )
        self.metrics["reports_total"].labels(*labels).inc()


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
