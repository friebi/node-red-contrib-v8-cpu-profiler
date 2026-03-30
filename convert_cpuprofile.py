#!/usr/bin/env python3
"""
convert_cpuprofile.py
---------------------
Converts a legacy V8 CPU profile (nested 'head' tree, startTime/endTime in
seconds) to the modern flat format expected by VS Code and Chrome DevTools.

Usage:
    python convert_cpuprofile.py <input.cpuprofile> [output.cpuprofile]

If the output path is omitted, the converted file is written next to the input
file with '_converted' appended before the extension.
"""

import json
import sys
from pathlib import Path


def flatten_nodes(node, nodes_list):
    """Recursively flatten a nested V8 profile tree into a flat node list."""
    children_ids = [child["id"] for child in node.get("children", [])]
    new_node = {
        "id": node["id"],
        "callFrame": {
            "functionName": node.get("functionName", ""),
            "scriptId": str(node.get("scriptId", 0)),
            "url": node.get("url", ""),
            "lineNumber": node.get("lineNumber", 0),
            "columnNumber": node.get("columnNumber", 0),
        },
        "hitCount": node.get("hitCount", 0),
        "children": children_ids,
    }
    bailout = node.get("bailoutReason", "")
    if bailout:
        new_node["deoptReason"] = bailout
    line_ticks = node.get("lineTicks", [])
    if line_ticks:
        new_node["positionTicks"] = [
            {"line": t["line"], "ticks": t["hitCount"]} for t in line_ticks
        ]
    nodes_list.append(new_node)
    for child in node.get("children", []):
        flatten_nodes(child, nodes_list)


def convert(input_path: Path, output_path: Path):
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "profile" in data:
        print("Legacy format with 'profile' wrapper detected – unwrapping.")
        data = json.loads(data["profile"])

    if "nodes" in data and "head" not in data:
        print("Profile already appears to be in the modern flat format – no conversion needed.")
        return

    # Flatten the nested head tree
    nodes = []
    flatten_nodes(data["head"], nodes)

    # startTime / endTime in the legacy format are in seconds;
    # the modern format uses microseconds.
    start_us = int(data["startTime"]) * 1_000_000
    end_us = int(data["endTime"]) * 1_000_000

    # Convert absolute timestamps → time deltas
    timestamps = data.get("timestamps", [])
    time_deltas = []
    for i, ts in enumerate(timestamps):
        if i == 0:
            time_deltas.append(max(0, ts - start_us))
        else:
            time_deltas.append(max(0, ts - timestamps[i - 1]))

    new_profile = {
        "nodes": nodes,
        "startTime": start_us,
        "endTime": end_us,
        "samples": data.get("samples", []),
        "timeDeltas": time_deltas,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(new_profile, f, separators=(",", ":"))

    print(f"Conversion complete.")
    print(f"  nodes     : {len(nodes)}")
    print(f"  samples   : {len(new_profile['samples'])}")
    print(f"  timeDeltas: {len(time_deltas)}")
    print(f"  startTime : {start_us}")
    print(f"  endTime   : {end_us}")
    print(f"  output    : {output_path}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_stem(input_path.stem + "_converted")

    convert(input_path, output_path)


if __name__ == "__main__":
    main()
