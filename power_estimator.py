import logging
import os
import json

import pwnagotchi.plugins as plugins

from flask import abort, render_template_string


TEMPLATE = """
{% extends "base.html" %}
{% set active_page = "powerbankStatus" %}

{% block title %}
    {{ title }}
{% endblock %}

{% block meta %}
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, user-scalable=0" />
{% endblock %}

{% block styles %}
{{ super() }}
    <style>
        .pb-form label {
            display: block;
            margin-top: 12px;
            font-weight: bold;
        }
        .pb-form input {
            width: 100%;
            box-sizing: border-box;
            padding: 8px;
            font-size: 1em;
            margin-top: 4px;
        }
        .pb-form button {
            margin-top: 16px;
            padding: 10px 20px;
            font-size: 1em;
        }
        .pb-message {
            margin-top: 12px;
            padding: 10px;
            font-weight: bold;
        }
        .pb-message.ok {
            background-color: #d4edda;
            color: #155724;
        }
        .pb-message.err {
            background-color: #f8d7da;
            color: #721c24;
        }
        .pb-estimate {
            margin-top: 20px;
            padding: 15px;
            background-color: #eee;
            border: 1px solid black;
        }
        .pb-estimate table {
            width: 100%;
        }
        .pb-estimate td {
            padding: 6px;
        }
    </style>
{% endblock %}

{% block content %}
    {% if message %}
        <div class="pb-message {{ 'ok' if message == 'Saved!' else 'err' }}">{{ message }}</div>
    {% endif %}

    <form class="pb-form" method="POST" action="">
        <label for="capacity_mah">Powerbank capacity (mAh)</label>
        <input type="number" step="1" min="1" name="capacity_mah" id="capacity_mah"
               value="{{ data.get('capacity_mah', '') }}" required>

        <label for="percent">Current charge (%)</label>
        <input type="number" step="0.1" min="0" max="100" name="percent" id="percent"
               value="{{ data.get('percent', '') }}" required>

        <label for="voltage">Voltage (V)</label>
        <input type="number" step="0.01" min="0.1" name="voltage" id="voltage"
               value="{{ data.get('voltage', '') }}" required>

        <label for="power_draw">Estimated average load (W)</label>
        <input type="number" step="0.01" min="0.01" name="power_draw" id="power_draw"
               value="{{ data.get('power_draw_w', 1.0) }}" required>

        <button type="submit">Save</button>
    </form>

    {% if estimate %}
        <div class="pb-estimate">
            <table>
                <tr><td>Remaining capacity:</td><td>{{ estimate.remaining_mah }} mAh</td></tr>
                <tr><td>Remaining energy:</td><td>{{ estimate.remaining_wh }} Wh</td></tr>
                <tr><td>Estimated runtime:</td>
                    <td>{{ estimate.days }}d {{ estimate.hours }}h {{ estimate.minutes }}m
                        ({{ estimate.hours_remaining }} h total)</td></tr>
            </table>
        </div>
    {% endif %}
{% endblock %}
"""


class power_estimator(plugins.Plugin):
    __author__ = 'avipars'
    __version__ = '0.0.5'
    __license__ = 'GPL3'
    __description__ = 'Estimate remaining powerbank runtime from capacity, charge %, voltage and load'

    def __init__(self):
        self.ready = False
        self.options = {}
        self.data_path = '/root/power_estimator.json'

    def on_loaded(self):
        logging.info("[power_estimator] plugin loaded")

    def on_config_changed(self, config):
        self.config = config
        # optional: [main.plugins.power_estimator] path = "/root/power_estimator.json"
        self.options = config.get('main', {}).get('plugins', {}).get('power_estimator', {}) or {}
        self.data_path = self.options.get('path', '/root/power_estimator.json')
        self.ready = True

    def _load_data(self):
        """Return the last-saved values as a dict, or {} if none/corrupt."""
        try:
            if os.path.isfile(self.data_path):
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (OSError, ValueError) as e:
            logging.warning("[power_estimator] could not read %s: %s" % (self.data_path, e))
        return {}

    def _save_data(self, data):
        try:
            os.makedirs(os.path.dirname(self.data_path) or '.', exist_ok=True)
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except OSError as e:
            logging.error("[power_estimator] could not write %s: %s" % (self.data_path, e))
            raise

    @staticmethod
    def _estimate(data):
        """
        Estimate remaining runtime.

        Voltage + mAh gives remaining energy in Wh:
            Wh_remaining = (capacity_mah / 1000) * (percent / 100) * voltage
        Dividing by an assumed average load in Watts gives hours remaining.
        There's no way to derive load from mAh/%/V alone, so 'power_draw_w'
        is a user-editable assumption (default 1.0 W, roughly a Pi Zero W
        class device running pwnagotchi) rather than a measured value.
        """
        try:
            capacity = float(data['capacity_mah'])
            percent = float(data['percent'])
            voltage = float(data['voltage'])
            power_draw = float(data.get('power_draw_w', 1.0))
            if capacity <= 0 or voltage <= 0 or power_draw <= 0:
                return None

            remaining_mah = capacity * (percent / 100.0)
            remaining_wh = (remaining_mah / 1000.0) * voltage
            hours_remaining = remaining_wh / power_draw

            total_minutes = int(round(hours_remaining * 60))
            days, rem_minutes = divmod(total_minutes, 24 * 60)
            hours, minutes = divmod(rem_minutes, 60)

            return {
                'remaining_mah': round(remaining_mah, 1),
                'remaining_wh': round(remaining_wh, 2),
                'hours_remaining': round(hours_remaining, 2),
                'days': days,
                'hours': hours,
                'minutes': minutes,
            }
        except (KeyError, ValueError, TypeError, ZeroDivisionError):
            return None

    def on_webhook(self, path, request):
        if not self.ready:
            return "Plugin not ready"

        if path != "/" and path:
            abort(404)

        try:
            data = self._load_data()
            message = None

            if request.method == "POST":
                try:
                    capacity = float(request.form.get("capacity_mah", "").strip())
                    percent = float(request.form.get("percent", "").strip())
                    voltage = float(request.form.get("voltage", "").strip())
                    power_draw = float(request.form.get("power_draw", "").strip())

                    if not (0 <= percent <= 100):
                        raise ValueError("charge %% must be between 0 and 100")
                    if capacity <= 0:
                        raise ValueError("capacity must be positive")
                    if voltage <= 0:
                        raise ValueError("voltage must be positive")
                    if power_draw <= 0:
                        raise ValueError("load must be positive")

                    data = {
                        "capacity_mah": capacity,
                        "percent": percent,
                        "voltage": voltage,
                        "power_draw_w": power_draw,
                    }
                    self._save_data(data)
                    message = "Saved!"
                except (ValueError, AttributeError) as ve:
                    message = "Error: %s" % ve

            estimate = self._estimate(data) if data else None

            return render_template_string(
                TEMPLATE,
                title="Powerbank Status",
                data=data or {},
                estimate=estimate,
                message=message,
            )
        except Exception as e:
            logging.error("[power_estimator] error: %s" % e)
            logging.debug(e, exc_info=True)
            abort(500)
