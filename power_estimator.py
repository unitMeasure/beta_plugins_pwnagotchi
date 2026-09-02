import logging
import os
import json
import time

import pwnagotchi.plugins as plugins

from flask import abort, render_template_string

try:
    from pwnagotchi.ui.components import LabeledValue
    from pwnagotchi.ui.view import BLACK
    import pwnagotchi.ui.fonts as fonts
except ImportError:
    # keeps the plugin importable in a non-pwnagotchi test env
    LabeledValue = None
    BLACK = None
    fonts = None


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
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <label for="capacity_mah">Powerbank capacity (mAh)</label>
        <input type="number" step="1" min="1" name="capacity_mah" id="capacity_mah"
               value="{{ data.get('capacity_mah', '5000') }}" required>

        <label for="percent">Current charge (%)</label>
        <input type="number" step="0.1" min="0" max="100" name="percent" id="percent"
               value="{{ data.get('percent', '60') }}" required>

        <label for="voltage">Voltage (V)</label>
        <input type="number" step="0.01" min="0.1" name="voltage" id="voltage"
               value="{{ data.get('voltage', '5') }}" required>

        <label for="power_draw">Estimated average load (W)</label>
        <input type="number" step="0.01" min="0.01" name="power_draw" id="power_draw"
               value="{{ data.get('power_draw_w', 2.9) }}" required>

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
    __version__ = '0.0.7'
    __license__ = 'GPL3'
    __description__ = 'Estimate remaining powerbank runtime from capacity, charge %, voltage and load'

    def __init__(self):
        self.ready = False
        self.options = {}
        self.data_path = '/root/power_estimator.json'

        # in-memory cache of the last known/estimated reading, so on_ui_update
        # doesn't have to hit disk on every tick
        self.current_data = {}

        # decay bookkeeping
        self._decay_interval_s = 300  # how often we re-estimate, in seconds
        self._last_decay_check = 0.0  # monotonic clock, throttles on_ui_update work

        # ui bookkeeping
        self._ui_enabled = True
        self._ui_added = False

    def on_loaded(self):
        logging.info("[power_estimator] plugin loaded")

    def on_config_changed(self, config):
        self.config = config
        # optional:
        # [main.plugins.power_estimator]
        # path = "/root/power_estimator.json"
        # ui = true
        # ui_x = 130
        # ui_y = 80
        # interval_minutes = 5
        self.options = config.get('main', {}).get('plugins', {}).get('power_estimator', {}) or {}
        self.data_path = self.options.get('path', '/root/power_estimator.json')
        self._ui_enabled = bool(self.options.get('ui', True))

        try:
            interval_minutes = float(self.options.get('interval_minutes', 5))
        except (TypeError, ValueError):
            interval_minutes = 5
        self._decay_interval_s = max(30.0, interval_minutes * 60.0)

        # prime the in-memory cache from disk so the ui has something to show
        # as soon as it's set up, without waiting for the first decay tick
        self.current_data = self._load_data()

        self.ready = True

    # ---------------------------------------------------------------- data

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

    @staticmethod
    def _decay_percent(data, elapsed_hours):
        """
        Given elapsed time since the last known reading, estimate how much
        charge % has been used up, assuming a constant power_draw_w load.

        current_A = power_draw_w / voltage
        mAh_used  = current_A * elapsed_hours * 1000
        pct_used  = mAh_used / capacity_mah * 100

        Returns the new (clamped) percent, or None if the stored reading
        doesn't have enough info to extrapolate from (e.g. never saved yet).
        """
        try:
            capacity = float(data['capacity_mah'])
            percent = float(data['percent'])
            voltage = float(data['voltage'])
            power_draw = float(data.get('power_draw_w', 1.0))
            if capacity <= 0 or voltage <= 0 or power_draw <= 0 or elapsed_hours <= 0:
                return percent

            current_a = power_draw / voltage
            mah_used = current_a * elapsed_hours * 1000.0
            pct_used = (mah_used / capacity) * 100.0

            return max(0.0, min(100.0, percent - pct_used))
        except (KeyError, ValueError, TypeError, ZeroDivisionError):
            return None

    def _apply_decay_if_due(self, now_monotonic):
        """
        Throttled (every _decay_interval_s) re-estimate of the current
        percentage, based on wall-clock time elapsed since the reading was
        last saved/estimated (a stand-in for "uptime" - time the powerbank
        has actually been draining). Updates self.current_data and persists
        it. Safe to call often; it no-ops between intervals.
        """
        if now_monotonic - self._last_decay_check < self._decay_interval_s:
            return
        self._last_decay_check = now_monotonic

        data = self.current_data or self._load_data()
        if not data or 'percent' not in data:
            return  # nothing saved yet, nothing to extrapolate from

        now_wall = time.time()
        last_update = data.get('last_update', now_wall)
        elapsed_hours = max(0.0, (now_wall - last_update) / 3600.0)
        if elapsed_hours <= 0:
            return

        new_percent = self._decay_percent(data, elapsed_hours)
        if new_percent is None:
            return

        data = dict(data)
        data['percent'] = round(new_percent, 2)
        data['last_update'] = now_wall

        try:
            self._save_data(data)
            self.current_data = data
        except OSError:
            # keep the in-memory estimate even if the disk write failed
            self.current_data = data

    # ------------------------------------------------------------------ ui

    def on_ui_setup(self, ui):
        if not self._ui_enabled or LabeledValue is None:
            return
        try:
            x = int(self.options.get('ui_x', 130))
            y = int(self.options.get('ui_y', 80))
            ui.add_element('pb', LabeledValue(
                color=BLACK,
                label='PB',
                value='-',
                position=(x, y),
                label_font=fonts.Small,
                text_font=fonts.Small,
            ))
            self._ui_added = True
        except Exception as e:
            logging.warning("[power_estimator] could not add ui element: %s" % e)

    def on_ui_update(self, ui):
        if not self.ready:
            return

        # cheap, throttled re-estimate (only touches disk every interval)
        self._apply_decay_if_due(time.monotonic())

        if not self._ui_enabled or not self._ui_added:
            return

        percent = (self.current_data or {}).get('percent')
        try:
            ui.set('pb', "%.0f%%" % float(percent) if percent is not None else '-')
        except (TypeError, ValueError):
            ui.set('pb', '-')

    def on_unload(self, ui):
        if self._ui_added:
            try:
                with ui._lock:
                    ui.remove_element('pb')
            except Exception:
                pass

    # -------------------------------------------------------------- webhook

    def on_webhook(self, path, request):
        if not self.ready:
            return "Plugin not ready"

        if path != "/" and path:
            abort(404)

        try:
            data = self.current_data or self._load_data()
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
                        "last_update": time.time(),
                    }
                    self._save_data(data)
                    self.current_data = data
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
            