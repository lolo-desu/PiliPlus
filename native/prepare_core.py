"""Copy the upstream protobuf codec unchanged into the native core build."""

from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parent.parent
target = root / "native/core/lib"
target.mkdir(parents=True, exist_ok=True)
manifest = {}
for name in ["v1.pb.dart", "v1.pbenum.dart"]:
    source = root / "lib/grpc/bilibili/community/service/dm" / name
    shutil.copyfile(source, target / name)
    manifest[str(source.relative_to(root))] = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
(target.parent / "upstream-sources.json").write_text(
    json.dumps(manifest, indent=2) + "\n"
)
