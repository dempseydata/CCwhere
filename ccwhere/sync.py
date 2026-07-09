"""`python -m ccwhere.sync` — run a sync and print the summary."""
import json

from . import ingest

if __name__ == "__main__":
    s = ingest.sync()
    unknown_share = (sum(s["unknown_types"].values()) / s["total_events"] * 100
                     if s["total_events"] else 0.0)
    print(f"files: {s['files_parsed']}/{s['files_scanned']} parsed · "
          f"events: {s['events_added']:,} added of {s['total_events']:,} seen · "
          f"bad lines: {s['bad_lines']} · "
          f"drift: {unknown_share:.1f}% unknown types · "
          f"{s['elapsed_ms']:,}ms")
    if s["unknown_types"]:
        print("unknown types:", json.dumps(s["unknown_types"]))
    if s["unknown_fields"]:
        print("unknown fields:", json.dumps(s["unknown_fields"]))
