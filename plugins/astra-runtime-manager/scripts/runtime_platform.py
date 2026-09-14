"""Inspect executable paths without reading process arguments or environment data."""

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


def relevant_name(name):
    return name.lower().startswith(('codex', 'chatgpt'))


def linux_executables(proc=Path('/proc')):
    if not proc.is_dir():
        raise ValueError('Linux /proc is unavailable; process status is unknown')
    result = []
    for process in proc.iterdir():
        if not process.name.isdigit():
            continue
        try:
            name = (process / 'comm').read_text().strip()
            if relevant_name(name):
                result.append(os.readlink(process / 'exe'))
        except (FileNotFoundError, ProcessLookupError):
            continue  # Process exited between listing and inspection.
    return result


def windows_executables(records):
    if records is None:
        raise ValueError('Windows process query returned no result')
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise ValueError('Unrecognized Windows process response')
    result = []
    for process in records:
        if not isinstance(process, dict) or not isinstance(process.get('Name'), str):
            raise ValueError('Incomplete Windows process response')
        if relevant_name(process['Name']):
            executable = process.get('ExecutablePath')
            if not isinstance(executable, str) or not executable:
                raise ValueError('Cannot inspect a Codex process executable; status is unknown')
            result.append(executable)
    return result


def running_executables():
    system = platform.system()
    if system == 'Linux':
        return linux_executables()
    if system == 'Darwin':
        return subprocess.check_output(['ps', '-axo', 'comm='], text=True, timeout=15).splitlines()
    if system == 'Windows':
        powershell = shutil.which('powershell') or shutil.which('pwsh')
        if not powershell:
            raise ValueError('PowerShell is required for Windows process inspection')
        query = ("$ErrorActionPreference='Stop'; "
                 "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
                 "@(Get-CimInstance Win32_Process | Select-Object Name,ExecutablePath) | ConvertTo-Json -Compress")
        response = subprocess.check_output([powershell, '-NoProfile', '-NonInteractive', '-Command', query],
                                           text=True, encoding='utf-8', timeout=15)
        return windows_executables(json.loads(response))
    raise ValueError('No process-inspection adapter for ' + system)
