#!/usr/bin/env python3
"""Generate HTML dashboard from analyze.py JSON output.

Takes a JSON file produced by analyze.py and renders a self-contained HTML
dashboard by injecting the data into a template.

Usage:
    python3 visualize.py <input.json> --mode scan|sleep|activity|heart|correlate|compare|yearly

Output: HTML to stdout.

The template is loaded from ../assets/dashboard-template.html relative to this
script. The placeholder <!--DATA_INJECTION--> is replaced with a <script> tag
that sets window.__DATA__ and window.__MODE__, which the template's JS reads
to render the appropriate dashboard.
"""

import argparse
import json
import os
import sys

VALID_MODES = ("scan", "sleep", "activity", "heart", "correlate", "compare", "yearly")


def build_html(data, mode, template_path=None):
    """Inject *data* (dict) and *mode* (str) into the dashboard template.

    Args:
        data: Parsed JSON dict from analyze.py output.
        mode: One of VALID_MODES.
        template_path: Optional override for the template file location.

    Returns:
        Complete HTML string ready to be written/served.
    """
    if template_path is None:
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "assets",
            "dashboard-template.html",
        )

    with open(template_path, "r") as f:
        template = f.read()

    # Build the injection script.  json.dumps handles escaping of special
    # characters (</script>, quotes, etc.) inside the JSON payload.
    injection = (
        "<script>"
        "window.__DATA__=" + json.dumps(data, default=str) + ";"
        "window.__MODE__=" + json.dumps(mode) + ";"
        "</script>"
    )

    html = template.replace("<!--DATA_INJECTION-->", injection)
    return html


def main():
    parser = argparse.ArgumentParser(
        description="Generate HTML dashboard from analyze.py JSON output.",
    )
    parser.add_argument(
        "input_file",
        help="JSON file produced by analyze.py",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=VALID_MODES,
        help="Dashboard mode (must match the analysis mode used to produce the JSON)",
    )

    args = parser.parse_args()

    # Read input JSON.
    try:
        with open(args.input_file, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading input file: {exc}", file=sys.stderr)
        sys.exit(1)

    # Build and emit.
    try:
        html = build_html(data, args.mode)
    except OSError as exc:
        print(f"Error reading template: {exc}", file=sys.stderr)
        sys.exit(1)

    sys.stdout.write(html)


if __name__ == "__main__":
    main()
