OmniSight: Micro-Telemetry Flight Recorder

OmniSight is an Ultra lightweight, asynchronous desktop framework written in Python and PyQt6. It functions like an airplane's black box for your operating system, capturing and aggregating micro-events (file modifications, renames, deletions, and process spawns) in real-time across your entire user profile.

Unlike traditional signature-based antivirus tools, SystemPulse focuses strictly on pure behavioral and filesystem telemetry visibility.

## Features

* **Asynchronous Multi-Threaded Engine (`QThread`)**: Background sniffing tasks do not lock, freeze, or throttle the user interface.
* **Full Profile Telemetry**: Monitors everything inside the active user directory (`~`), catching background operating system operations and hidden app hooks.
* **Event Inspector**: Click on any row in the feed to safely load the full, uncropped plaintext telemetry block.
* **Immutable Audit Trail**: Includes anti-crash safeguards against empty rows or missing system items, and an export pipeline to write logs to raw CSV spreadsheets.
* **Modern Minimal UI**: Engineered with a high-contrast white layout featuring rounded components and a dynamic, high-refresh terminal loading wheel.

## Core Prerequisites

Ensure your environment satisfies the following system-level dependencies:

```bash
pip install PyQt6 watchdog psutil
```

## System Architecture

The project is architected into three main modules:
1. **The Telemetry Engine (Backend)**: Houses the `FileSystemEventHandler` (`watchdog`) and process table sampling loop (`psutil`) inside a persistent background execution pipeline.
2. **The Event Aggregator**: A real-time data conduit that maps host system structural fields into standardized thread-safe `pyqtSignal` events.
3. **The Control Panel (Frontend UI)**: Built on `PyQt6`, rendering dynamic emojis, computing real-time host metric overheads (CPU/RAM), and enforcing a strict newest-event-first grid ordering.

## Getting Started

1. Place the 3 structural Python blocks sequentially into a single file named `OmniSight.py`.
2. Open a terminal and run the main entry point:
   ```bash
   OmniSight.py
   ```
3. Interact with your operating system (create a file on your Desktop, launch a terminal, or edit a configuration script) to view the telemetry grid populate instantly.

## Schema Layout (CSV Export / Inspector Output)

Exported audit sheets map to the following structural matrix:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `TIMESTAMP` | String | Precise system execution clock mapped to the millisecond (`HH:M:S.f`). |
| `SUBSYSTEM` | String | System engine boundary origin flag (`FILESYSTEM` / `PROCESS`). |
| `ACTION` | String | Execution verb captured by host hooks (`CREATED`, `DELETED`, `MOVED`, `SPAWN`). |
| `TARGET_ENTITY` | String | Base binary name or filename target of the telemetry handle. |
| `RAW_DETAILS` | String | Complete host absolute pathing strings or deep argument strings. |

## License

MIT - Free for open-source modification and individual security engineering tooling.
