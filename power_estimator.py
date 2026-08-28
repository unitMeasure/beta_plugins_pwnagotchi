"""
Power Bank Estimator Plugin for Pwnagotchi

Adds a web interface at /plugins/power-estimator where you can enter
the current power bank percentage and capacity (mAh). It uses the
system uptime to estimate how much battery life remains, assuming
the power bank was at 100% when the Pwnagotchi started.

Configuration (config.toml):
    main.plugins.power-estimator.enabled = true
"""

import logging
import os
import time
import pwnagotchi
import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts


class PowerEstimator(plugins.Plugin):
    __author__ = "wsvdmeer"
    __editor__ = "avipars"
    __version__ = "0.0.1"
    __license__ = "GPL3"
    __description__ = "Web UI to estimate remaining power bank life"

    def on_loaded(self):
        logging.info("[power-estimator] Plugin loaded")

    def on_webhook(self, path, request):
        if path != "power-estimator":
            return None

        # Get uptime in seconds
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
        uptime_hours = uptime_seconds / 3600.0

        # Handle form submission
        percentage = None
        capacity = None
        remaining_hours = None
        remaining_str = ""

        if request.method == "POST":
            try:
                percentage = float(request.form.get('percentage', 0))
                capacity = float(request.form.get('capacity', 0))
                if percentage < 0 or percentage > 100:
                    raise ValueError
                if capacity <= 0:
                    raise ValueError

                # Estimate remaining time (in hours)
                # Formula: remaining = uptime * percentage / (100 - percentage)
                if percentage < 100:
                    remaining_hours = uptime_hours * percentage / (100 - percentage)
                else:
                    remaining_hours = float('inf')  # Can't estimate if still 100%

                if remaining_hours == float('inf'):
                    remaining_str = "x (battery still at 100%)"
                else:
                    # Format nicely
                    days = int(remaining_hours // 24)
                    hours = int(remaining_hours % 24)
                    minutes = int((remaining_hours * 60) % 60)
                    if days > 0:
                        remaining_str = f"{days}d {hours}h {minutes}m"
                    elif hours > 0:
                        remaining_str = f"{hours}h {minutes}m"
                    else:
                        remaining_str = f"{minutes}m"

                # Also calculate used/remaining capacity
                used_capacity = capacity * (1 - percentage / 100)
                remaining_capacity = capacity * percentage / 100
                logging.info(
                    f"[power-estimator] Percentage={percentage}%, Capacity={capacity}mAh, "
                    f"Remaining={remaining_str}, Uptime={uptime_hours:.2f}h"
                )
            except (ValueError, TypeError):
                remaining_str = "Invalid input"

        # Build HTML
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Power Bank Estimator</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: #1a1a2e;
                    color: #fff;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                }
                .container {
                    background: rgba(255,255,255,0.1);
                    padding: 30px;
                    border-radius: 15px;
                    width: 90%;
                    max-width: 400px;
                }
                h1 { text-align: center; margin-bottom: 20px; }
                label { display: block; margin: 10px 0 5px; }
                input {
                    width: 100%;
                    padding: 10px;
                    border: none;
                    border-radius: 5px;
                    background: rgba(255,255,255,0.2);
                    color: #fff;
                    font-size: 16px;
                }
                button {
                    width: 100%;
                    padding: 12px;
                    margin-top: 20px;
                    background: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 16px;
                    cursor: pointer;
                }
                button:hover { background: #45a049; }
                .result {
                    margin-top: 20px;
                    padding: 15px;
                    background: rgba(0,0,0,0.3);
                    border-radius: 5px;
                    text-align: center;
                    font-size: 18px;
                }
                .uptime {
                    text-align: center;
                    margin-bottom: 15px;
                    font-size: 14px;
                    opacity: 0.8;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔋 Power Bank Estimator</h1>
                <div class="uptime">System uptime: {uptime:.2f} hours</div>
                <form method="POST">
                    <label for="percentage">Current Battery Percentage (%):</label>
                    <input type="number" id="percentage" name="percentage" min="0" max="100" step="0.1" required value="{perc_val}">

                    <label for="capacity">Power Bank Capacity (mAh):</label>
                    <input type="number" id="capacity" name="capacity" min="1" step="any" required value="{cap_val}">

                    <button type="submit">Estimate Remaining Time</button>
                </form>
                {result_html}
            </div>
        </body>
        </html>
        """.format(
            uptime=round(uptime_hours, 2),
            perc_val=percentage if percentage is not None else "",
            cap_val=capacity if capacity is not None else "",
            result_html=f'<div class="result">Remaining: {remaining_str}</div>' if remaining_str else ""
        )

        return html
