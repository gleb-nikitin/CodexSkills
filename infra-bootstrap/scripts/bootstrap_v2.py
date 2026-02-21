#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import shlex
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


class StepError(RuntimeError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__(message)
        self.step = step
        self.message = message


def run_cmd(cmd: list[str], step: str) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise StepError(step, f"command failed ({proc.returncode}): {' '.join(cmd)} | {stderr}")
    return proc


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StepError("load_config", f"config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StepError("load_config", f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise StepError("load_config", "config root must be an object")
    return data


def require_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise StepError("validate_config", f"missing object: {key}")
    return value


def require_str(data: dict[str, Any], key: str, step: str = "validate_config") -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StepError(step, f"missing string field: {key}")
    return value.strip()


def require_list_of_str(data: dict[str, Any], key: str, step: str = "validate_config") -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and x.strip() for x in value):
        raise StepError(step, f"missing non-empty string list: {key}")
    return [x.strip() for x in value]


def parse_port(value: Any) -> int:
    if value is None:
        return 22
    if isinstance(value, bool):
        raise StepError("validate_config", "invalid integer for server.port: bool is not allowed")
    if isinstance(value, int):
        port = value
    elif isinstance(value, str):
        v = value.strip()
        if not v:
            raise StepError("validate_config", "invalid integer for server.port: empty value")
        try:
            port = int(v)
        except ValueError as exc:
            raise StepError("validate_config", f"invalid integer for server.port: {value!r}") from exc
    else:
        raise StepError("validate_config", f"invalid integer for server.port: {value!r}")
    if port <= 0 or port > 65535:
        raise StepError("validate_config", f"invalid server.port range: {port}")
    return port


def parse_config(path: Path) -> dict[str, Any]:
    # Strict explicit-contract parser: reject missing/invalid fields early.
    data = load_json(path)

    server = require_dict(data, "server")
    dataset = require_dict(data, "dataset")
    model = require_dict(data, "model")
    python_checks = require_dict(data, "python_checks")

    cfg: dict[str, Any] = {
        "server": {
            "host": require_str(server, "host"),
            "port": parse_port(server.get("port", 22)),
            "ssh_key": str(Path(require_str(server, "ssh_key")).expanduser()),
        },
        "dataset": {
            "local_path": str(Path(require_str(dataset, "local_path")).expanduser()),
            "remote_path": require_str(dataset, "remote_path"),
        },
        "model": {
            "local_path": str(Path(require_str(model, "local_path")).expanduser()),
            "remote_path": require_str(model, "remote_path"),
        },
        "python_checks": {
            "python_bin": require_str({"python_bin": python_checks.get("python_bin", "python3")}, "python_bin"),
            "required_imports": require_list_of_str(python_checks, "required_imports"),
        },
        "remote_dirs": require_list_of_str(data, "remote_dirs"),
    }

    ds_local = Path(cfg["dataset"]["local_path"])
    if not ds_local.exists() or not ds_local.is_dir():
        raise StepError("validate_config", f"dataset.local_path is not a directory: {ds_local}")

    model_local = Path(cfg["model"]["local_path"])
    if not model_local.exists() or not model_local.is_file():
        raise StepError("validate_config", f"model.local_path is not a file: {model_local}")

    ssh_key = Path(cfg["server"]["ssh_key"])
    if not ssh_key.exists() or not ssh_key.is_file():
        raise StepError("validate_config", f"server.ssh_key is not a file: {ssh_key}")

    return cfg


def build_ssh_base(cfg: dict[str, Any]) -> list[str]:
    server = cfg["server"]
    return [
        "ssh",
        "-i",
        server["ssh_key"],
        "-p",
        str(server["port"]),
        "-o",
        "StrictHostKeyChecking=accept-new",
        server["host"],
    ]


def run_remote(cfg: dict[str, Any], remote_cmd: str, step: str) -> subprocess.CompletedProcess[str]:
    cmd = build_ssh_base(cfg) + [remote_cmd]
    return run_cmd(cmd, step)


def rsync_to_remote(cfg: dict[str, Any], source: str, target: str, step: str, destructive: bool) -> None:
    server = cfg["server"]
    rsync_cmd = [
        "rsync",
        "-avP",
        "-e",
        f"ssh -i {shlex.quote(server['ssh_key'])} -p {server['port']} -o StrictHostKeyChecking=accept-new",
    ]
    if destructive:
        rsync_cmd.append("--delete")
    rsync_cmd.extend([source, f"{server['host']}:{target}"])
    run_cmd(rsync_cmd, step)


def remote_file_size(cfg: dict[str, Any], path: str) -> int:
    proc = run_remote(
        cfg,
        f"python3 -c {shlex.quote(f'import os; p=\"{path}\"; print(os.path.getsize(p) if os.path.exists(p) else -1)')}",
        "check_model_remote",
    )
    out = proc.stdout.strip()
    return int(out) if out.lstrip("-").isdigit() else -1


def append_step(report: dict[str, Any], step: str, status: str, details: dict[str, Any] | None = None) -> None:
    report["steps"].append({"step": step, "status": status, "details": details or {}})


def cmd_validate(config_path: Path) -> int:
    cfg = parse_config(config_path)
    preview = {
        "status": "ok",
        "validated": True,
        "config": str(config_path),
        "server": cfg["server"]["host"],
        "dataset_local": cfg["dataset"]["local_path"],
        "dataset_remote": cfg["dataset"]["remote_path"],
        "model_local": cfg["model"]["local_path"],
        "model_remote": cfg["model"]["remote_path"],
        "remote_dirs": cfg["remote_dirs"],
    }
    print(json.dumps(preview, indent=2, ensure_ascii=True))
    return 0


def cmd_setup(config_path: Path, report_path: Path | None, destructive: bool) -> int:
    # Keep report paths unique even for rapid consecutive runs.
    now = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    run_id = uuid.uuid4().hex[:8]
    if report_path is None:
        report_path = Path.cwd() / "logs" / "infra" / f"bootstrap_v2_{now}_{run_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "version": "infra-bootstrap-v2",
        "started_utc": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "status": "running",
        "config": str(config_path),
        "destructive": destructive,
        "steps": [],
    }

    cfg: dict[str, Any] | None = None
    try:
        # Parse config inside try so config failures are also captured in report.
        cfg = parse_config(config_path)

        run_remote(cfg, "echo connected", "connect_server")
        append_step(report, "connect_server", "ok")

        gpu = run_remote(cfg, "nvidia-smi --query-gpu=name --format=csv,noheader", "verify_gpu")
        gpu_names = [x.strip() for x in gpu.stdout.splitlines() if x.strip()]
        if not gpu_names:
            raise StepError("verify_gpu", "nvidia-smi returned no GPU devices")
        append_step(report, "verify_gpu", "ok", {"gpus": gpu_names})

        dirs = " ".join(shlex.quote(d) for d in cfg["remote_dirs"])
        run_remote(cfg, f"mkdir -p {dirs}", "ensure_remote_dirs")
        append_step(report, "ensure_remote_dirs", "ok", {"count": len(cfg["remote_dirs"])})

        dataset_remote = cfg["dataset"]["remote_path"].rstrip("/") + "/"
        run_remote(cfg, f"mkdir -p {shlex.quote(cfg['dataset']['remote_path'])}", "ensure_dataset_dir")
        rsync_to_remote(
            cfg,
            cfg["dataset"]["local_path"].rstrip("/") + "/",
            dataset_remote,
            "upload_dataset",
            destructive,
        )
        append_step(report, "upload_dataset", "ok", {"remote_path": cfg["dataset"]["remote_path"]})

        model_local = Path(cfg["model"]["local_path"])
        model_remote = cfg["model"]["remote_path"]
        run_remote(cfg, f"mkdir -p {shlex.quote(str(Path(model_remote).parent))}", "ensure_model_dir")

        local_size = model_local.stat().st_size
        current_remote_size = remote_file_size(cfg, model_remote)
        uploaded = False
        if current_remote_size != local_size:
            rsync_to_remote(cfg, str(model_local), model_remote, "ensure_base_model", False)
            uploaded = True
        append_step(
            report,
            "ensure_base_model",
            "ok",
            {
                "remote_path": model_remote,
                "local_size": local_size,
                "remote_size_before": current_remote_size,
                "uploaded": uploaded,
            },
        )

        checks = cfg["python_checks"]
        remote_python = checks["python_bin"]
        imports = checks["required_imports"]
        check_script = (
            f"{shlex.quote(remote_python)} - <<'PY'\n"
            "import importlib, json\n"
            f"required = {json.dumps(imports)}\n"
            "missing=[]\n"
            "for name in required:\n"
            "    try:\n"
            "        importlib.import_module(name)\n"
            "    except Exception:\n"
            "        missing.append(name)\n"
            "print(json.dumps({'missing': missing}))\n"
            "PY"
        )
        checks_proc = run_remote(cfg, check_script, "validate_python_imports")
        payload = json.loads(checks_proc.stdout.strip() or "{}")
        missing = payload.get("missing", [])
        if missing:
            raise StepError("validate_python_imports", f"missing imports: {', '.join(missing)}")
        append_step(report, "validate_python_imports", "ok", {"checked": imports})

        report["status"] = "ok"
        return 0
    except StepError as exc:
        append_step(report, exc.step, "failed", {"error": exc.message})
        report["status"] = "failed"
        report["failed_step"] = exc.step
        report["error"] = exc.message
        print(f"ERROR [{exc.step}] {exc.message}", file=sys.stderr)
        return 1
    except Exception as exc:
        message = f"unexpected error: {exc}"
        append_step(report, "internal_error", "failed", {"error": message})
        report["status"] = "failed"
        report["failed_step"] = "internal_error"
        report["error"] = message
        print(f"ERROR [internal_error] {message}", file=sys.stderr)
        return 1
    finally:
        report["finished_utc"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        print(str(report_path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic Vast.ai bootstrap v2")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="Run deterministic bootstrap using explicit config.")
    setup.add_argument("--config", required=True, type=Path, help="Path to bootstrap config JSON.")
    setup.add_argument("--report", type=Path, default=None, help="Optional report path.")
    setup.add_argument(
        "--destructive",
        action="store_true",
        help="Allow delete-like sync behavior (enables rsync --delete for dataset upload).",
    )

    validate = sub.add_parser("validate-config", help="Validate config without connecting to remote host.")
    validate.add_argument("--config", required=True, type=Path, help="Path to bootstrap config JSON.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate-config":
        return cmd_validate(args.config)
    if args.command == "setup":
        return cmd_setup(args.config, args.report, args.destructive)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
