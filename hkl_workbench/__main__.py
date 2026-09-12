"""One offline entry point for the five research tracks."""
import argparse
import sys
from pathlib import Path

from .common import load_inputs, provenance, write_json
from .experiments import e1, e2, e3, e4
from .evaluation import e5
from .model import validate
from .packet_reader import verify
from .preservation import unpack_packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["slice", "run", "verify-packet", "unpack"])
    parser.add_argument("--output", type=Path, default=Path("work/slice"))
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--split", choices=["development", "holdout", "all"], default="all")
    args = parser.parse_args()
    if args.command == "verify-packet":
        if args.packet is None:
            parser.error("verify-packet requires --packet")
        print(verify(args.packet))
        return 0
    if args.command == "unpack":
        if args.archive is None:
            parser.error("unpack requires --archive")
        print(unpack_packet(args.archive, args.output))
        return 0
    corpus, profile = load_inputs()
    errors = validate(corpus, profile)
    if errors:
        raise ValueError("\n".join(errors))
    receipt = provenance("python -m hkl_workbench " + " ".join(sys.argv[1:]))
    args.output.mkdir(parents=True, exist_ok=False)
    results = {"provenance": receipt, "E1": e1(corpus, profile), "E3": e3(corpus, profile, args.output, receipt)}
    tracks = ["E1", "E3"]
    if args.command == "run":
        results.update(E2=e2(corpus, profile), E4=e4(corpus, profile), E5=e5(corpus, profile, args.split))
        tracks += ["E2", "E4"]
    write_json(args.output / "results.json", results)
    if not all(c["passed"] for track in tracks for c in results[track]["checks"]):
        raise ValueError("experiment behavior check failed; inspect results.json")
    if args.command == "run":
        if not all(c["passed"] for c in results["E5"]["controls"]):
            raise ValueError("retrieval control failed")
        if any(v["aggregate"]["disclosure_failures"]["failures"] or v["aggregate"]["unsupported_selection"]["unsupported"] for v in results["E5"]["variants"].values()):
            raise ValueError("retrieval safety gate failed")
    print(("WORKBENCH VERIFIED" if args.command == "run" else "SLICE VERIFIED: E1 and E3") + "; " + str(args.output / "results.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
