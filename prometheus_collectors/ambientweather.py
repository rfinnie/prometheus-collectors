# SPDX-FileComment: prometheus-ambientweather - Ambient Weather
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
        "baromabsin": ("barometer_absolute_in", "outdoor"),
        "baromrelin": ("barometer_relative_in", "outdoor"),
        "dailyrainin": ("daily_rain_in", "outdoor"),
        "dewPoint": ("dew_point_f", "outdoor"),
        "dewPointin": ("dew_point_f", "indoor"),
        "eventrainin": ("event_rain_in", "outdoor"),
        "feelsLike": ("feels_like_f", "outdoor"),
        "feelsLikein": ("feels_like_f", "indoor"),
        "hourlyrainin": ("hourly_rain_in", "outdoor"),
        "humidity": ("humidity_percent", "outdoor"),
        "humidityin": ("humidity_percent", "indoor"),
        "maxdailygust": ("max_daily_gust_mph", "outdoor"),
        "monthlyrainin": ("monthly_rain_in", "outdoor"),
        "solarradiation": ("solar_radiation_wm2", "outdoor"),
        "temp1f": ("temperature_f", "pool"),
        "tempf": ("temperature_f", "outdoor"),
        "tempinf": ("temperature_f", "indoor"),
        "uv": ("uv_index", "outdoor"),
        "weeklyrainin": ("weekly_rain_in", "outdoor"),
        "winddir": ("wind_direction", "outdoor"),
        "winddir_avg10m": ("wind_direction_avg10m", "outdoor"),
        "windgustmph": ("wind_gust_mph", "outdoor"),
        "windspdmph_avg10m": ("wind_speed_avg10m_mph", "outdoor"),
        "windspeedmph": ("wind_speed_mph", "outdoor"),
        "yearlyrainin": ("yearly_rain_in", "outdoor"),
    }

    def setup(self):
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
            if not self.args.http_daemon:
                raise RuntimeError("Only --http-daemon is supported for receiver mode")

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
            self.metric(self.sensor_map[k][0], labels).set(v)

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
            self.collector.metric("collection_time", {"site": site_name}).set(
                time.time()
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
