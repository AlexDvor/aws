"""Run directly from the project directory without installing a package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from aws_cost_guard.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
