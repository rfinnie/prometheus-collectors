# SPDX-FileComment: things-collector
# SPDX-FileCopyrightText: Copyright (C) 2021 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Sample things.yaml:
#
# hubs:
# - name: hubitat
#   url: http://hubitat.example.lan
#   access_token: 2c24f2f8-5457-4f7d-be29-1778c28e3531
#   temp_fahrenheit: true

import sys

import dateutil.parser
import dateutil.tz

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "things"
    needs_config = True
    needs_requests = True

    def setup(self):
        defs = [
            ("reports", "counter", "Total reports received"),
            ("device.time.seconds", "gauge", "Thing device check-in time"),
            ("temperature.degrees.celsius", "gauge", "Thing temperature"),
            ("battery.percent", "gauge", "Thing battery"),
            ("illuminance.lux", "gauge", "Thing illuminance"),
            ("humidity.percent", "gauge", "Thing humidity"),
            ("switch.on", "gauge", "1 if the switch is on"),
            ("light.level.percent", "gauge", "Light level percent"),
        ]

        for k, t, h in defs:
            self.create_instrument(t, k, description=h)

    def collect_metrics(self):
        for hub in self.config["hubs"]:
            self.collect_hub(hub)

    def collect_hub(self, hub):
        r = self.r_session.get(
            "{}/apps/api/4/devices/all?access_token={}".format(
                hub["url"], hub["access_token"]
            )
        )
        r.raise_for_status()

        for thing in r.json():
            self.process_thing(thing, hub)

    def process_thing(self, thing, hub):
        if "attributes" not in thing:
            return

        # The hub's "temperature" field can be C or F (user preference).
        # We'll always coax it into C.
        is_f = hub.get("temp_fahrenheit", False)

        labels = {"hub": hub["name"]}
        for name in ("id", "label", "manufacturer", "model", "name", "type"):
            labels[name] = thing[name] if thing[name] is not None else ""

        for g, k, f in [
            (
                "temperature.degrees.celsius",
                "temperature",
                lambda x: ((float(x) - 32) / 1.8) if is_f else float(x),
            ),
            ("battery.percent", "battery", float),
            ("illuminance.lux", "illuminance", float),
            ("humidity.percent", "humidity", float),
            ("switch.on", "switch", lambda x: 1 if x == "on" else 0),
            ("light.level.percent", "level", float),
        ]:
            v = thing["attributes"].get(k)
            if v is None:
                continue
            try:
                v = f(v)
            except Exception:
                self.logger.exception(
                    "Encountered an attribute error for {} ({})".format(
                        thing["label"], thing["id"]
                    )
                )
                continue

            self.instruments[g].set(v, labels)

        if thing["date"]:
            thing_date = dateutil.parser.parse(thing["date"])
            if thing_date.tzinfo is None:
                thing_date = thing_date.astimezone(dateutil.tz.tzlocal())
            self.instruments["device.time.seconds"].set(
                float(thing_date.strftime("%s")), labels
            )
        self.instruments["reports"].add(1, labels)


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
