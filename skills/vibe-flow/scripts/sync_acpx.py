"""Refresh exact upstream skill and license from the pinned npm package."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import urllib.request

DEST = Path(__file__).resolve().parents[3] / "vendor/acpx"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="fetch and compare, do not write")
    args = parser.parse_args(argv)
    try:
        source = json.loads((DEST / "SOURCE.json").read_text(encoding="utf-8"))
        with urllib.request.urlopen(source["source"], timeout=30) as response:
            packed = response.read()
        contents = {}
        with tarfile.open(fileobj=io.BytesIO(packed), mode="r:gz") as archive:
            manifest = json.load(archive.extractfile("package/package.json"))
            if manifest["name"] != source["package"] or manifest["version"] != source["version"]:
                raise ValueError("upstream package/version does not match SOURCE.json")
            for target, member in source["files"].items():
                if Path(target).name != target:
                    raise ValueError("invalid vendor filename")
                contents[target] = archive.extractfile(member).read()
        results = []
        for name, data in contents.items():
            path = DEST / name
            changed = not path.exists() or path.read_bytes() != data
            results.append({"file":name,"changed":changed,"sha256":hashlib.sha256(data).hexdigest()})
            if changed and not args.dry_run:
                path.write_bytes(data)
        print(json.dumps({"dry_run":args.dry_run,"version":source["version"],"files":results},indent=2))
        return 0
    except (OSError, ValueError, KeyError, tarfile.TarError) as exc:
        print(f"sync acpx: {exc}",file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
