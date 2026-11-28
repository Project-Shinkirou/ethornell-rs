#!/usr/bin/env python3
"""Test the adapter and record its locked Cargo cdylib build."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "crates/shinki-emu-ethornell-rs/Cargo.toml"
PACKAGE = "shinki-emu-ethornell-rs"
PLUGIN = "ethornell-rs"
FEATURE = "diagnostic-bridge"
TARGETS = {
    "x86_64-pc-windows-msvc": "standalone",
    "x86_64-unknown-linux-gnu": "standalone",
    "aarch64-apple-darwin": "standalone",
    "x86_64-apple-darwin": "standalone",
    "aarch64-linux-android": "standalone",
    "x86_64-linux-android": "standalone",
    "aarch64-apple-ios": "signed-input",
    "aarch64-apple-ios-sim": "signed-input",
    "x86_64-apple-ios": "signed-input",
}

NDK_REV = "30.0.16248370"
ANDROID_API = 28


def setup_android(target, env):
    sdk = env.get("ANDROID_HOME") or env.get("ANDROID_SDK_ROOT")
    configured = env.get("ANDROID_NDK_HOME") or env.get("ANDROID_NDK_ROOT")
    if env.get("GITHUB_ACTIONS") == "true":
        # Runner images may point ANDROID_NDK_HOME at a different revision.
        if not sdk:
            raise RuntimeError("Android SDK with sdkmanager is required")
        manager = str(Path(sdk) / "cmdline-tools/latest/bin/sdkmanager")
        run(manager, f"--sdk_root={sdk}", "--licenses", input="y\n" * 100,
            stdout=subprocess.DEVNULL, text=True, env=env)
        run(manager, f"--sdk_root={sdk}", "--channel=0", f"ndk;{NDK_REV}", env=env)
        ndk = Path(sdk) / "ndk" / NDK_REV
    elif configured:
        ndk = Path(configured)
    elif sdk:
        ndk = Path(sdk) / "ndk" / NDK_REV
    else:
        raise RuntimeError(f"Set ANDROID_NDK_HOME to Android NDK {NDK_REV}")
    ndk = ndk.resolve()
    properties = {}
    for line in (ndk / "source.properties").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            properties[key.strip()] = value.strip()
    if properties.get("Pkg.Revision") != NDK_REV:
        raise RuntimeError(f"Expected Android NDK {NDK_REV} at {ndk}")
    tools = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    clang = tools / f"{target}{ANDROID_API}-clang"
    clangxx = tools / f"{target}{ANDROID_API}-clang++"
    ar = tools / "llvm-ar"
    if not all(tool.is_file() for tool in (clang, clangxx, ar)):
        raise RuntimeError(f"Android API {ANDROID_API} toolchain is incomplete for {target}")
    key = target.replace("-", "_")
    env.update({
        "ANDROID_NDK_HOME": str(ndk),
        f"CARGO_TARGET_{key.upper()}_LINKER": str(clang),
        f"CC_{key}": str(clang), f"CXX_{key}": str(clangxx), f"AR_{key}": str(ar),
    })
    export_for_closure(env, "ANDROID_NDK_HOME")



def run(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def export_for_closure(env, name):
    if path := env.get("GITHUB_ENV"):
        with Path(path).open("a", encoding="utf-8") as stream:
            print(f"{name}={env[name]}", file=stream)


def setup_host(host, env):
    if host == "x86_64-pc-windows-msvc":
        if env.get("VSCMD_ARG_TGT_ARCH") != "x64":
            vswhere = Path(env["PROGRAMFILES(X86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
            install = run(
                str(vswhere), "-latest", "-products", "*", "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath",
                capture_output=True, text=True, env=env,
            ).stdout.strip()
            if not install:
                raise RuntimeError("Visual Studio x64 C++ build tools are required")
            vcvars = Path(install) / "VC/Auxiliary/Build/vcvars64.bat"
            shell = env["COMSPEC"]
            # cmd.exe needs native quoting, not the C argv quoting used for a list.
            settings = subprocess.check_output(
                f'"{shell}" /d /s /c ""{vcvars}" >nul && set"',
                executable=shell, text=True, cwd=ROOT, env=env,
            )
            for line in settings.splitlines():
                if "=" in line and not line.startswith("="):
                    key, value = line.split("=", 1)
                    env[key.upper()] = value
        redist = env.pop("VCTOOLSREDISTDIR", None) or env.get("VCToolsRedistDir")
        if not redist or not (Path(redist) / "x64").is_dir():
            raise RuntimeError("Visual Studio x64 redistributables are required")
        env["VCToolsRedistDir"] = redist
        export_for_closure(env, "VCToolsRedistDir")
    elif host == "x86_64-unknown-linux-gnu" and env.get("GITHUB_ACTIONS") == "true":
        run("sudo", "apt-get", "update", env=env)
        run("sudo", "apt-get", "install", "-y", "pkg-config", "libasound2-dev",
            "libxkbcommon-dev", "libwayland-dev", env=env)
    elif host.endswith("-apple-darwin"):
        env["MACOSX_DEPLOYMENT_TARGET"] = "13.0"


def verify_report(path, target):
    library = None
    reports = {}
    finished = False
    extension = ".dll" if target.endswith("windows-msvc") else ".dylib" if "-apple-" in target else ".so"
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            message = json.loads(line)
            if finished:
                raise RuntimeError("Unexpected Cargo message after build-finished")
            match message.get("reason"):
                case "build-script-executed":
                    reports[message["package_id"]] = Path(message["out_dir"]) / "core-build.json"
                case "compiler-artifact" if "cdylib" in message["target"]["crate_types"]:
                    if Path(message["manifest_path"]).resolve() == ROOT / MANIFEST:
                        images = [Path(name) for name in message["filenames"] if Path(name).suffix == extension]
                        if library is not None or len(images) != 1 or not images[0].is_file():
                            raise RuntimeError("Expected exactly one adapter cdylib in the Cargo report")
                        library = message["package_id"], images[0]
                case "build-finished":
                    finished = message["success"]
    if not finished or library is None:
        raise RuntimeError("No successful Cargo build of the adapter cdylib")
    report = json.loads(reports[library[0]].read_text(encoding="utf-8"))
    if (report["plugin_id"], report["target"], report["artifact_kind"]) != (PLUGIN, target, "rust-cdylib"):
        raise RuntimeError("Core build report does not match the requested release adapter")
    return library[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=TARGETS)
    parser.add_argument("--mode", required=True, choices=sorted(set(TARGETS.values())))
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    target = args.target
    if args.mode != TARGETS[target]:
        parser.error(f"{target} requires {TARGETS[target]} mode")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    messages = out / "cargo.jsonl"
    partial = out / "cargo.jsonl.partial"
    messages.unlink(missing_ok=True)
    partial.unlink(missing_ok=True)

    env = os.environ.copy()
    host = run("rustc", "--print", "host-tuple", capture_output=True, text=True, env=env).stdout.strip()
    apple_mobile = "-apple-ios" in target
    android = target.endswith("-linux-android")
    expected_host = target
    if apple_mobile:
        expected_host = target.split("-")[0] + "-apple-darwin"
    if android:
        expected_host = "x86_64-unknown-linux-gnu"
    if host != expected_host:
        parser.error(f"{target} requires a {expected_host} runner, found {host}")
    setup_host(host, env)
    env.setdefault("CARGO_TARGET_DIR", str(out.parent / "cargo-target"))
    env.setdefault("SHINKI_EMU_WORK_ROOT", str(out.parent / "native-work"))
    flags = ["--manifest-path", MANIFEST, "--locked", "--release", "--lib", "-p", PACKAGE,
             "--no-default-features", "--features", FEATURE]
    print(f"Running {PACKAGE} tests on {host}", flush=True)
    run("cargo", "test", *flags, "--target", host, env=env)

    target_env = env.copy()
    if android:
        setup_android(target, target_env)
    if apple_mobile:
        sdk = "iphoneos" if target == "aarch64-apple-ios" else "iphonesimulator"
        target_env.pop("MACOSX_DEPLOYMENT_TARGET", None)
        target_env["IPHONEOS_DEPLOYMENT_TARGET"] = "16.0"
        target_env["SDKROOT"] = run("xcrun", "--sdk", sdk, "--show-sdk-path",
                                    capture_output=True, text=True, env=target_env).stdout.strip()
    run("rustup", "target", "add", target, env=env)
    print(f"Building {PACKAGE} for {target} ({args.mode})", flush=True)
    with partial.open("wb") as stream:
        build = subprocess.run(
            ("cargo", "build", *flags, "--target", target, "--message-format=json"),
            env=target_env, cwd=ROOT, stdout=stream,
        )
    if build.returncode:
        with partial.open(encoding="utf-8") as stream:
            for line in stream:
                if rendered := json.loads(line).get("message", {}).get("rendered"):
                    print(rendered, file=sys.stderr, end="")
        build.check_returncode()
    image = verify_report(partial, target)
    partial.replace(messages)
    summary = f"{PACKAGE}: tests passed on {host}; release {image.name} built for {target} ({args.mode})."
    print(summary)
    if path := env.get("GITHUB_STEP_SUMMARY"):
        with Path(path).open("a", encoding="utf-8") as stream:
            print(summary, file=stream)


if __name__ == "__main__":
    main()
