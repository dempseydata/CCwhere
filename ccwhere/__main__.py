"""ccwhere entry point: sync, serve, open browser. Ctrl-C stops (ADR-0001)."""
import argparse
import sys
import webbrowser

from . import ingest, server


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="ccwhere",
        description="See where your tokens got burned.")
    ap.add_argument("--port", type=int, default=8917)
    ap.add_argument("--no-browser", action="store_true",
                    help="do not open the dashboard in a browser")
    args = ap.parse_args(argv)

    try:
        srv = server.make_server(args.port)
    except OSError:
        print(f"ccwhere: port {args.port} is already in use. "
              f"Try --port <other>.", file=sys.stderr)
        return 1

    s = ingest.sync()
    print(f"synced: {s['files_parsed']}/{s['files_scanned']} files, "
          f"{s['events_added']:,} events, {s['elapsed_ms']:,}ms")

    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"dashboard: {url}  (Ctrl-C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
