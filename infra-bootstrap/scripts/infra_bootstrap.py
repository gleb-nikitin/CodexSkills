#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_REQUIRED_PACKAGES = ["torch", "torchvision", "accelerate", "safetensors"]


@dataclass
class ServerConfig:
    name: str
    host: str
    port: int
    ssh_key: str
    dataset_base: str = "/workspace/datasets"
    workspace_dir: str = "/workspace"
    model_dir: str = "/workspace/models/sdxl"
    python_bin: str = "python3"


@dataclass
class DatasetInfo:
    name: str
    path: Path
    image_count: int
    caption_count: int


class ActionLogger:
    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        self.jsonl_path = root / f"infra_bootstrap_{ts}.jsonl"
        self.report_path = root / f"infra_bootstrap_{ts}.json"
        self.events: list[dict[str, Any]] = []

    def log(self, level: str, action: str, **data: Any) -> None:
        event = {
            "ts_utc": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "level": level,
            "action": action,
            "data": data,
        }
        self.events.append(event)
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=True) + "\n")
        print(f"[{level}] {action}")

    def finalize(self, status: str) -> None:
        payload = {
            "status": status,
            "created_utc": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "events": self.events,
            "jsonl": str(self.jsonl_path),
        }
        self.report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def run_cmd(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc


def detect_project_root(start: Path) -> Path:
    for candidate in [start] + list(start.parents):
        if (candidate / "AGENTS.md").exists() and (candidate / "scripts").exists():
            return candidate
    raise RuntimeError("Cannot detect project root from current location.")


def detect_environment() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "local-mac"
    if system == "linux":
        if shutil.which("nvidia-smi"):
            return "remote-linux-gpu"
        return "linux-no-gpu"
    return f"unknown-{system}"


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def parse_datasets_md(path: Path) -> dict[str, DatasetInfo]:
    out: dict[str, DatasetInfo] = {}
    if not path.exists():
        return out
    lines = path.read_text(encoding="utf-8").splitlines()
    header_idx = None
    headers: list[str] = []
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "Dataset" in line and "Local path" in line:
            header_idx = i
            headers = [h.strip().lower() for h in line.strip().strip("|").split("|")]
            break
    if header_idx is None:
        return out
    for line in lines[header_idx + 2 :]:
        raw = line.strip()
        if not raw.startswith("|"):
            if raw:
                break
            continue
        cols = [c.strip() for c in raw.strip("|").split("|")]
        if len(cols) != len(headers):
            continue
        row = dict(zip(headers, cols))
        name = row.get("dataset", "")
        local_path = row.get("local path", "")
        if not name or not local_path:
            continue
        p = Path(local_path).expanduser()
        if not p.exists() or not p.is_dir():
            continue
        image_count, caption_count = count_dataset_files(p)
        out[name] = DatasetInfo(name=name, path=p, image_count=image_count, caption_count=caption_count)
    return out


def count_dataset_files(path: Path) -> tuple[int, int]:
    image_count = 0
    caption_count = 0
    for f in path.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() in IMAGE_EXTS:
            image_count += 1
            if f.with_suffix(".txt").exists():
                caption_count += 1
    return image_count, caption_count


def discover_datasets(project_root: Path) -> dict[str, DatasetInfo]:
    discovered = parse_datasets_md(project_root / "datasets.md")
    candidate_roots = [
        project_root / "datasets",
        project_root / "data" / "datasets",
        Path(os.environ.get("DATASETS_ROOT", "")).expanduser() if os.environ.get("DATASETS_ROOT") else None,
    ]
    for root in candidate_roots:
        if not root or not root.exists() or not root.is_dir():
            continue
        for d in sorted(x for x in root.iterdir() if x.is_dir()):
            image_count, caption_count = count_dataset_files(d)
            if image_count == 0:
                continue
            discovered.setdefault(
                d.name,
                DatasetInfo(name=d.name, path=d, image_count=image_count, caption_count=caption_count),
            )
    return discovered


def discover_servers(project_root: Path) -> dict[str, ServerConfig]:
    servers: dict[str, ServerConfig] = {}
    config_candidates = [
        Path(os.environ.get("INFRA_BOOTSTRAP_SERVERS", "")).expanduser() if os.environ.get("INFRA_BOOTSTRAP_SERVERS") else None,
        project_root / "config" / "servers.json",
        project_root / "templates" / "servers.json",
        project_root / "skills" / "infra-bootstrap" / "references" / "servers.local.json",
    ]
    for cfg in config_candidates:
        if not cfg or not cfg.exists():
            continue
        content = json.loads(cfg.read_text(encoding="utf-8"))
        source = content.get("servers", content)
        if not isinstance(source, dict):
            continue
        for name, item in source.items():
            if not isinstance(item, dict):
                continue
            try:
                servers[name] = ServerConfig(
                    name=name,
                    host=item["host"],
                    port=int(item.get("port", 22)),
                    ssh_key=str(Path(item.get("ssh_key", "~/.ssh/ed25519_NoPass")).expanduser()),
                    dataset_base=item.get("dataset_base", "/workspace/datasets"),
                    workspace_dir=item.get("workspace_dir", "/workspace"),
                    model_dir=item.get("model_dir", "/workspace/models/sdxl"),
                    python_bin=item.get("python_bin", "python3"),
                )
            except KeyError:
                continue
    return servers


def resolve_server(server_name: str, project_root: Path) -> ServerConfig:
    servers = discover_servers(project_root)
    if server_name in servers:
        return servers[server_name]
    if server_name in {"env", "default", "vast"}:
        host = os.environ.get("VAST_SSH_HOST")
        port = int(os.environ.get("VAST_SSH_PORT", "22"))
        ssh_key = os.environ.get("VAST_SSH_KEY")
        if not host or not ssh_key:
            raise RuntimeError(
                "Server config not found. Provide config/servers.json or set VAST_SSH_HOST/VAST_SSH_KEY environment vars."
            )
        return ServerConfig(name=server_name, host=host, port=port, ssh_key=str(Path(ssh_key).expanduser()))
    raise RuntimeError(
        f"Unknown server '{server_name}'. Add it to config/servers.json or use --server env with VAST_SSH_* variables."
    )


def build_ssh_cmd(server: ServerConfig, remote_cmd: str) -> list[str]:
    return [
        "ssh",
        "-i",
        server.ssh_key,
        "-p",
        str(server.port),
        "-o",
        "StrictHostKeyChecking=accept-new",
        server.host,
        remote_cmd,
    ]


def run_remote(server: ServerConfig, remote_cmd: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_cmd(build_ssh_cmd(server, remote_cmd), check=check)


def verify_nas_access(allow_missing: bool, logger: ActionLogger) -> None:
    nas = Path("/mnt/nas")
    if not nas.exists() or not os.access(nas, os.R_OK):
        msg = "NAS mount /mnt/nas is unavailable or not readable."
        if allow_missing:
            logger.log("WARN", "nas_unavailable", message=msg)
            return
        raise RuntimeError(msg)
    logger.log("INFO", "nas_ok", path=str(nas))


def choose_dataset(dataset_name: str, datasets: dict[str, DatasetInfo]) -> DatasetInfo:
    if dataset_name in datasets:
        return datasets[dataset_name]
    lowered = {k.lower(): v for k, v in datasets.items()}
    if dataset_name.lower() in lowered:
        return lowered[dataset_name.lower()]
    available = ", ".join(sorted(datasets))
    raise RuntimeError(f"Dataset '{dataset_name}' not found. Available: {available}")


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def locate_snapshot(snapshot_name: str) -> Path:
    roots = [Path("/mnt/nas/snapshots"), Path("/mnt/nas/models"), Path("/mnt/nas")]
    for root in roots:
        if not root.exists():
            continue
        direct = root / snapshot_name
        if direct.exists():
            return direct
        candidates = list(root.rglob(snapshot_name))
        if candidates:
            return candidates[0]
    raise RuntimeError(f"Snapshot '{snapshot_name}' not found under /mnt/nas")


def remote_file_size(server: ServerConfig, path: str) -> int:
    cmd = f"python3 -c {shlex.quote(f'import os; print(os.path.getsize(\"{path}\"))')}"
    proc = run_remote(server, cmd, check=False)
    if proc.returncode != 0:
        return -1
    text = proc.stdout.strip()
    return int(text) if text.isdigit() else -1


def ensure_remote_dirs(server: ServerConfig, dirs: list[str]) -> None:
    quoted = " ".join(shlex.quote(d) for d in dirs)
    run_remote(server, f"mkdir -p {quoted}")


def upload_dataset(server: ServerConfig, dataset: DatasetInfo, remote_dataset_dir: str, logger: ActionLogger) -> None:
    ensure_remote_dirs(server, [remote_dataset_dir])
    rsync_cmd = [
        "rsync",
        "-avP",
        "-e",
        f"ssh -i {shlex.quote(server.ssh_key)} -p {server.port} -o StrictHostKeyChecking=accept-new",
        str(dataset.path) + "/",
        f"{server.host}:{remote_dataset_dir}/",
    ]
    run_cmd(rsync_cmd)
    logger.log(
        "INFO",
        "dataset_uploaded",
        dataset=dataset.name,
        local_path=str(dataset.path),
        remote_path=remote_dataset_dir,
        images=dataset.image_count,
        captions=dataset.caption_count,
    )


def sync_dataset_to_storage(
    dataset: DatasetInfo,
    project_root: Path,
    allow_missing_nas: bool,
    logger: ActionLogger,
) -> None:
    stage_root = Path(os.environ.get("INFRA_BOOTSTRAP_STAGE_DIR", str(project_root / "datasets_updates"))).expanduser()
    stage_dir = stage_root / dataset.name
    stage_dir.mkdir(parents=True, exist_ok=True)

    run_cmd(["rsync", "-a", "--delete", str(dataset.path) + "/", str(stage_dir) + "/"])
    logger.log("INFO", "dataset_staged_local", dataset=dataset.name, stage_dir=str(stage_dir))

    nas_datasets_root = Path("/mnt/nas/datasets")
    if not nas_datasets_root.exists():
        msg = "NAS datasets path /mnt/nas/datasets is unavailable."
        if allow_missing_nas:
            logger.log("WARN", "nas_datasets_unavailable", message=msg)
            return
        raise RuntimeError(msg)

    nas_target = nas_datasets_root / dataset.name
    nas_target.mkdir(parents=True, exist_ok=True)
    run_cmd(["rsync", "-a", "--delete", str(stage_dir) + "/", str(nas_target) + "/"])
    logger.log("INFO", "dataset_synced_to_nas", dataset=dataset.name, nas_path=str(nas_target))


def ensure_snapshot(
    server: ServerConfig,
    project_root: Path,
    snapshot_override: str | None,
    strict_hash: bool,
    logger: ActionLogger,
) -> None:
    models_env = parse_env_file(project_root / "config" / "models.env")
    base_model = models_env.get("SDXL_BASE_MODEL", "")
    snapshot_name = snapshot_override or (Path(base_model).name if base_model else "")
    if not snapshot_name:
        raise RuntimeError("Cannot resolve snapshot name. Set SDXL_BASE_MODEL in config/models.env or pass --snapshot.")

    local_snapshot = locate_snapshot(snapshot_name)
    local_size = local_snapshot.stat().st_size
    local_hash = compute_sha256(local_snapshot) if strict_hash else ""

    remote_snapshot = f"{server.model_dir.rstrip('/')}/{snapshot_name}"
    ensure_remote_dirs(server, [server.model_dir])
    size_remote = remote_file_size(server, remote_snapshot)

    upload_needed = size_remote != local_size
    if upload_needed:
        rsync_cmd = [
            "rsync",
            "-avP",
            "-e",
            f"ssh -i {shlex.quote(server.ssh_key)} -p {server.port} -o StrictHostKeyChecking=accept-new",
            str(local_snapshot),
            f"{server.host}:{server.model_dir}/",
        ]
        run_cmd(rsync_cmd)

    if strict_hash:
        remote_hash_cmd = (
            f"python3 -c {shlex.quote(f'import hashlib; p=\"{remote_snapshot}\"; h=hashlib.sha256(); '
            f'\\nwith open(p,\"rb\") as f:\\n '
            f'   [h.update(c) for c in iter(lambda:f.read(1048576), b\"\")]; '
            f'print(h.hexdigest())')}"
        )
        remote_hash_proc = run_remote(server, remote_hash_cmd)
        remote_hash = remote_hash_proc.stdout.strip()
        if remote_hash != local_hash:
            raise RuntimeError("Snapshot hash mismatch after upload.")
    logger.log(
        "INFO",
        "snapshot_ready",
        snapshot=snapshot_name,
        local_path=str(local_snapshot),
        remote_path=remote_snapshot,
        size_bytes=local_size,
        hash_checked=strict_hash,
        uploaded=upload_needed,
    )


def validate_remote_python(server: ServerConfig, required_packages: list[str], logger: ActionLogger) -> None:
    check_cmd = (
        f"{shlex.quote(server.python_bin)} - <<'PY'\n"
        "import importlib, json\n"
        f"pkgs = {json.dumps(required_packages)}\n"
        "missing=[]\n"
        "for p in pkgs:\n"
        "    try:\n"
        "        importlib.import_module(p)\n"
        "    except Exception:\n"
        "        missing.append(p)\n"
        "print(json.dumps({'missing': missing}))\n"
        "PY"
    )
    proc = run_remote(server, check_cmd)
    result = json.loads(proc.stdout.strip() or "{}")
    missing = result.get("missing", [])
    if missing:
        raise RuntimeError(f"Remote python missing packages: {', '.join(missing)}")
    logger.log("INFO", "python_env_ok", python_bin=server.python_bin, packages=required_packages)


def write_dataset_registry(datasets: dict[str, DatasetInfo], out_path: Path) -> None:
    payload = {
        "generated_utc": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "datasets": [
            {
                "name": d.name,
                "path": str(d.path),
                "images": d.image_count,
                "captions": d.caption_count,
                "captions_match_images": d.image_count == d.caption_count,
            }
            for d in sorted(datasets.values(), key=lambda x: x.name.lower())
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def setup(args: argparse.Namespace) -> int:
    project_root = detect_project_root(Path.cwd())
    log_dir = project_root / "logs" / "infra"
    logger = ActionLogger(log_dir)

    try:
        env_name = detect_environment()
        script_files = sorted(str(p.relative_to(project_root)) for p in (project_root / "scripts").glob("*.sh"))
        template_files = sorted(str(p.relative_to(project_root)) for p in (project_root / "templates").glob("*.json"))
        logger.log(
            "INFO",
            "environment_detected",
            environment=env_name,
            project_root=str(project_root),
            scripts_found=len(script_files),
            templates_found=len(template_files),
        )

        verify_nas_access(args.allow_missing_nas, logger)

        datasets = discover_datasets(project_root)
        if not datasets:
            raise RuntimeError("No datasets discovered. Add datasets dir or valid local paths in datasets.md.")
        registry_path = log_dir / f"dataset_registry_{dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
        write_dataset_registry(datasets, registry_path)
        logger.log("INFO", "dataset_registry_written", path=str(registry_path), datasets=len(datasets))

        dataset = choose_dataset(args.dataset, datasets)
        if dataset.image_count != dataset.caption_count:
            raise RuntimeError(
                f"Dataset '{dataset.name}' has mismatch: images={dataset.image_count}, captions={dataset.caption_count}"
            )

        server = resolve_server(args.server, project_root)
        logger.log("INFO", "server_resolved", server=server.name, host=server.host, port=server.port)

        remote_dataset_dir = f"{server.dataset_base.rstrip('/')}/{dataset.name}"
        ensure_remote_dirs(
            server,
            [
                server.workspace_dir,
                server.dataset_base,
                server.model_dir,
                f"{server.workspace_dir.rstrip('/')}/out_lora",
                f"{server.workspace_dir.rstrip('/')}/logs",
            ],
        )
        logger.log("INFO", "workspace_prepared", workspace=server.workspace_dir)

        if not args.skip_storage_sync:
            sync_dataset_to_storage(dataset, project_root, args.allow_missing_nas, logger)

        if not args.skip_upload:
            upload_dataset(server, dataset, remote_dataset_dir, logger)

        if not args.skip_snapshot:
            ensure_snapshot(server, project_root, args.snapshot, args.strict_hash, logger)

        validate_remote_python(server, args.required_package, logger)

        logger.log("INFO", "setup_completed", dataset=dataset.name, server=server.name)
        logger.finalize("ok")
        return 0
    except Exception as exc:
        logger.log("ERROR", "setup_failed", error=str(exc))
        logger.finalize("failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap and validate Vast.ai training infrastructure.")
    sub = parser.add_subparsers(dest="command", required=True)

    setup_p = sub.add_parser("setup", help="Run end-to-end infrastructure bootstrap.")
    setup_p.add_argument("--dataset", required=True, help="Dataset name to upload.")
    setup_p.add_argument("--server", required=True, help="Server name from config or 'env'.")
    setup_p.add_argument("--snapshot", default=None, help="Snapshot filename override.")
    setup_p.add_argument("--strict-hash", action="store_true", help="Compute and compare full SHA-256 for snapshot.")
    setup_p.add_argument("--skip-storage-sync", action="store_true", help="Skip local->NAS dataset synchronization.")
    setup_p.add_argument("--skip-upload", action="store_true", help="Skip dataset upload step.")
    setup_p.add_argument("--skip-snapshot", action="store_true", help="Skip snapshot verification/download step.")
    setup_p.add_argument("--allow-missing-nas", action="store_true", help="Warn instead of failing when /mnt/nas is missing.")
    setup_p.add_argument(
        "--required-package",
        action="append",
        default=DEFAULT_REQUIRED_PACKAGES.copy(),
        help="Remote python package that must be importable. Can be repeated.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "setup":
        return setup(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
