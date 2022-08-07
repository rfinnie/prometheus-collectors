# SPDX-FileComment: prometheus-ambientweather - ambientweather PVS5/PVS6
# SPDX-FileCopyrightText: Copyright (C) 2022 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

import sys

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
        self.api_url = self.config.get(
            "api_url",
            "https://rt.ambientweather.net/v1/devices?applicationKey={application_key}&apiKey={api_key}",
        ).format(
            application_key=self.config["application_key"],
            api_key=self.config["api_key"],
        )
        self.api_timeout = self.config.get("api_timeout", 15)

    def collect_metrics(self):
        r = self.r_session.get(self.api_url, timeout=self.api_timeout)
        r.raise_for_status()
        for site in r.json():
            for k, v in site["lastData"].items():
                if k not in self.sensor_map:
                    continue
                labels = {
                    "site": site["info"]["name"],
                    "sensor": self.sensor_map[k][1],
                }
                self.metric(self.sensor_map[k][0], labels).set(v)


def main(argv=None):
    sys.exit(Metrics().main(argv))


def module_init():
    if __name__ == "__main__":
        sys.exit(main(sys.argv))


module_init()
