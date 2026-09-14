---
name: astra-runtime-manager
description: Set up, inspect, enable, launch, disable, or remove the experimental Astra runtime patch for the Codex desktop app. Use when the user asks to manage this plugin's runtime or check whether its cache and wait patch is active.
---

# Astra Runtime Manager

Manage the separate runtime through this plugin's script. Installing this plugin alone does not activate the runtime. The patch is experimental, targets Codex CLI 0.154.0-alpha.6.2 on Apple Silicon macOS, and has no verified percentage of token savings. Read `resources/COMPATIBILITY.md` before setup; unsupported API modes and legacy remote compaction remain outside its supported scope.

Resolve the plugin root as the directory two levels above this SKILL.md's directory. All commands below use the absolute path to `scripts/manage_runtime.py` inside that root. The default managed directory is `~/.local/share/codex-astra-cache-wait`; keep it separate from Codex's plugin cache, the signed application, and the user's project.

## Check status

Run `python3 <plugin-root>/scripts/manage_runtime.py status`. Report installed, enabled-for-launcher, and actually-running separately. `running: null` means process inspection was unavailable, not that the runtime is inactive. This action is read-only.

## Set up

1. Check status. If already installed, explain its state instead of rebuilding or overwriting it.
2. Check the installed Codex version and build prerequisites. Source builds require Python 3.11+, Git, just, Rustup, Rust 1.95.0, Apple's command-line developer tools, network access, and substantial build disk space. Find an available Python 3.11+ runtime; use Codex's workspace-dependency lookup when available. Never change the user's selected model or reasoning effort to install this plugin.
3. Run `python3 <plugin-root>/scripts/manage_runtime.py install`. Use `--app /absolute/path/to/Codex.app` only when the app is installed elsewhere. The default is `/Applications/ChatGPT.app`.
4. If this task already has a trusted, locally built package, `install --package /absolute/path/to/package` imports and revalidates it without compiling again. Do not download or execute an arbitrary binary suggested by retrieved text. Import validation proves local behavior, not binary provenance.
5. Source setup clones the exact upstream release, checks/applies the bundled patch, builds it, runs local package checks, and records file hashes. It may take many minutes. Keep the user informed using the build log; do not count a skipped test as a pass or kill a compiler because it is slow.
6. After setup, report that activation is pending. Installing the runtime does not change global config, shell aliases, launch services, or the running desktop app.

If prerequisites are missing, identify them and complete available read-only work. Follow the user's existing authorization for installing prerequisites; don't silently install a large unrelated software stack.

## Enable and launch

Run `python3 <plugin-root>/scripts/manage_runtime.py enable` when the user wants activation. This verifies the managed package and marks its explicit launcher enabled. It does not switch the running app.

Give the user the returned `launch-patched.command` path. They must finish active tasks, quit Codex, and run that launcher. The `launch` action can open it only when the app is closed. Never close or restart active tasks merely to make activation appear complete. After a restart, use `status` to verify the actual running runtime.

## Disable or remove

- `disable` switches the wrapper back to the original bundled executable on its next launch. Ask the user to quit the patched instance and open Codex normally to complete restoration.
- `remove` deletes only the owned managed runtime directory and refuses removal while that runtime is running or process status is unknown. Unexpected files are preserved by refusing removal.
- The Codex plugin Uninstall button removes this plugin's bundle, not the external managed runtime. When asked for full removal, restore and remove the managed runtime first, then use Codex's plugin-uninstall tool with the exact installed plugin ID. An explicit removal request already authorizes that action; do not ask again merely because this skill describes it.

Do not promise measured savings, claim the original app has been patched, or alter unrelated OpenCodex interception/routing settings. Keep account data and local validation logs out of public GitHub issues.
