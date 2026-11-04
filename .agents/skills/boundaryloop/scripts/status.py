"""Invoke the real CLI; this script grants no execution or approval authority."""

from boundaryloop.cli import main

raise SystemExit(main(["--json", "status"]))
