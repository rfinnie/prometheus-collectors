# SPDX-FileComment: ambientweather-collector - Ambient Weather
# SPDX-FileCopyrightText: Copyright (C) 2022 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

# Default mode is to poll from ambientweather.net.  Create a set of API
# keys at https://ambientweather.net/account and then add them to the
# config:
#
#     data_mode: api
#     application_key: 1234aaaa1234aaaa1234aaaa1234aaaa1234aaaa1234aaaa1234aaaa1234aaaa
#     api_key: 5678bbbb5678bbbb5678bbbb5678bbbb5678bbbb5678bbbb5678bbbb5678bbbb
#
# Data will be sorted by site, as specified by the API output.
#
# Alternatively, The WS-2000 (and probably others) can be set to post
# directly to an arbitrary URL, and the collector can be set up to
# receive that.  On the control unit, go to Settings, Weather Server,
# Customized Setup:
#
#     State: Enable
#     Protocol Type: Same As AMBWeather
#     IP/Hostname: [collector address]
#     Port: 8000
#     Interval: 16 Second [lowest]
#     Path: /data/report/?
#
# Note the path must have a trailing "?", but can otherwise be any path.
# And the corresponding config:
#
#     data_mode: receiver
#     data_port: 8000
#     site_map:
#       - mac: "98:cd:ac:aa:bb:cc"
#         site: My Site
#
# Site name is mapped to a specified corresponding mac given by the
# control unit.

import sys
import time
import urllib.parse

from . import BaseMetrics


class Metrics(BaseMetrics):
    prefix = "ambientweather"
    needs_config = True
    needs_requests = True

    sensor_map = {
        "baromabsin": ("barometer.absolute.in", "outdoor"),
        "baromrelin": ("barometer.relative.in", "outdoor"),
        "dailyrainin": ("daily.rain.in", "outdoor"),
        "dewPoint": ("dew.point.f", "outdoor"),
        "dewPointin": ("dew.point.f", "indoor"),
        "eventrainin": ("event.rain.in", "outdoor"),
        "feelsLike": ("feels.like.f", "outdoor"),
        "feelsLikein": ("feels.like.f", "indoor"),
        "hourlyrainin": ("hourly.rain.in", "outdoor"),
        "humidity": ("humidity.percent", "outdoor"),
        "humidityin": ("humidity.percent", "indoor"),
        "maxdailygust": ("max.daily.gust.mph", "outdoor"),
        "monthlyrainin": ("monthly.rain.in", "outdoor"),
        "solarradiation": ("solar.radiation.wm2", "outdoor"),
        "temp1f": ("temperature.f", "pool"),
        "tempf": ("temperature.f", "outdoor"),
        "tempinf": ("temperature.f", "indoor"),
        "uv": ("uv.index", "outdoor"),
        "weeklyrainin": ("weekly.rain.in", "outdoor"),
        "winddir": ("wind.direction", "outdoor"),
        "winddir.avg10m": ("wind.direction.avg10m", "outdoor"),
        "windgustmph": ("wind.gust.mph", "outdoor"),
        "windspdmph.avg10m": ("wind.speed.avg10m.mph", "outdoor"),
        "windspeedmph": ("wind.speed.mph", "outdoor"),
        "yearlyrainin": ("yearly.rain.in", "outdoor"),
    }

    def pre_setup(self):
        if self.config.get("data_mode", "api") == "receiver":
            self.needs_periodic_export = True

    def setup(self):
        for k in {x[0] for x in self.sensor_map.values()}:
            self.create_instrument("gauge", k)
        self.create_instrument("gauge", "collection.time")

        self.data_mode = self.config.get("data_mode", "api")
        if self.data_mode == "api":
            self.api_url = self.config.get(
                "api_url",
                "https://rt.ambientweather.net/v1/devices?applicationKey={application_key}&apiKey={api_key}",
            ).format(
                application_key=self.config["application_key"],
                api_key=self.config["api_key"],
            )
            self.api_timeout = self.config.get("api_timeout", 15)
        elif self.data_mode == "receiver":
            from wsgiref.simple_server import make_server

            self.site_map = {
                x["mac"].lower(): x["site"] for x in self.config.get("site_map", [])
            }
            application = WSGIApplication(self)
            self.wsgi_server = make_server(
                "0.0.0.0", self.config.get("data_port", 8000), application
            )
        else:
            raise RuntimeError("Unknown data_mode")

    def collect_metrics(self):
        r = self.r_session.get(self.api_url, timeout=self.api_timeout)
        r.raise_for_status()
        for site in r.json():
            self.parse_metrics(site["lastData"], site["info"]["name"])

    def parse_metrics(self, data, site_name):
        for k, v in data.items():
            if k not in self.sensor_map:
                continue
            labels = {
                "site": site_name,
                "sensor": self.sensor_map[k][1],
            }
            self.instruments[self.sensor_map[k][0]].set(float(v), labels)

    def main_loop(self):
        if self.data_mode == "api":
            return super(Metrics, self).main_loop()
        elif self.data_mode == "receiver":
            return self.wsgi_server.serve_forever()


class WSGIApplication:
    def __init__(self, collector):
        self.collector = collector

    def __call__(self, environ, start_response):
        query_params = urllib.parse.parse_qs(environ.get("QUERY_STRING", ""))
        mac = None
        if query_params.get("PASSKEY", []):
            mac = query_params["PASSKEY"][0]
        elif query_params.get("MAC", []):
            mac = query_params["MAC"][0]
        if mac:
            site_name = self.collector.site_map[mac.lower()]
            self.collector.parse_metrics(
                {k: v[0] for k, v in query_params.items()},
                site_name,
            )
            self.collector.instruments["collection.time"].set(
                time.time(), {"site": site_name}
            )
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/plain; charset=UTF-8"),
                ("Content-Length", "3"),
            ],
        )
        return [b"ok\n"]


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
