"""One offline entry point for the five research tracks."""
import argparse
import sys
from pathlib import Path

from .common import load_inputs, provenance, write_json
from .experiments import e1, e3
from .model import validate
from .packet_reader import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["slice", "verify-packet"])
    parser.add_argument("--output", type=Path, default=Path("work/slice"))
    parser.add_argument("--packet", type=Path)
    args = parser.parse_args()
    if args.command == "verify-packet":
        print(verify(args.packet))
        return 0
    corpus, profile = load_inputs()
    errors = validate(corpus, profile)
    if errors:
        raise ValueError("\n".join(errors))
    receipt = provenance("python -m hkl_workbench " + " ".join(sys.argv[1:]))
    args.output.mkdir(parents=True, exist_ok=False)
    results = {"provenance": receipt, "E1": e1(corpus, profile), "E3": e3(corpus, profile, args.output, receipt)}
    write_json(args.output / "results.json", results)
    if not all(c["passed"] for track in ("E1", "E3") for c in results[track]["checks"]):
        raise ValueError("experiment behavior check failed; inspect results.json")
    print("SLICE VERIFIED: E1 and E3; " + str(args.output / "results.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
