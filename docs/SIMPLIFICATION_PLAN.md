# Simplification Plan: Image Segregation System

**Goal:** Reduce complexity to what’s actually needed, then make it faster. Plan first, implement later.

---

## 1. What the system really does (core job)

In one sentence:

> **Read images from a source folder → detect faces → match to registered people → write matched images into each person’s output folder.**

Everything else exists to support, configure, or harden that.

---

## 2. Current architecture map

### 2.1 Layers and modules

| Layer        | Modules / concepts | What they do |
|-------------|--------------------|--------------|
| **Entry**   | `main.py`          | FastAPI app, 3 pages (home, operator, tracker), 2 API routers |
| **API**     | `operator.py`      | 12 endpoints: job-config, persons CRUD, seed-person, add-reference, start/stop job, job-status, browse-folders, images-in-folder |
|             | `tracker.py`       | 2 endpoints: progress (from JSON files), worker-status (from heartbeat) |
| **Config**  | `config.py`        | ~25 settings: paths, thresholds, batch size, CPU modes, raw_cache, io_prefetch, batch_db_commits, etc. |
| **DB**      | `db.py`            | aiosqlite, WAL, get_db, get_db_transaction |
|             | `jobs.py`          | job_config, jobs, images, batches, image_results, commit_log, batch state machine helpers |
|             | `registry.py`      | persons, person_embeddings, person_centroids, CRUD + centroid logic |
|             | `schema.sql`       | 10+ tables, indexes, UNIQUEs |
| **Engine**  | `batch_engine.py`  | Orchestrates: ingest → process batch (state machine) → commit; ties together all engines |
|             | `ingest.py`        | Discovery, optional hashing, batch creation, selected_image_paths, one-per-stem (jpg vs arw) |
|             | `faces.py`         | InsightFace (detect + embed) |
|             | `match.py`         | Match to centroids, STRICT/LOOSE thresholds, optional learning |
|             | `raw_convert.py`   | ARW → temp JPEG (recognition), ARW → deliverable JPEG |
|             | `compress.py`      | JPEG → deliverable (resize, sRGB, quality) |
|             | `routing.py`       | Staging → fan-out to person folders, commit_log, idempotency, `CommitReconciliation` |
| **State**   | `state_writer.py`  | progress.json, batches/*.json, atomic writes |
| **Storage** | `paths.py`         | `PathManager` (unused in routing), `StorageError`, `compute_file_hash`, `generate_deterministic_filename` |
| **Worker**  | `runner.py`        | Loop: config check → discover → process batches → heartbeat; resume logic |

### 2.2 Concepts that add complexity

- **Batch state machine:** PENDING → PROCESSING → COMMITTING → COMMITTED, with resume/reconciliation.
- **Commit log:** Idempotency and crash recovery for writes (commit_log, check_output_exists_in_log, update_commit_status, `CommitReconciliation`).
- **Two UIs:** Operator (control) and Tracker (read-only); separate API surfaces.
- **Two processes:** Server (API + pages) and Worker (batch loop), talking via DB + JSON files.
- **Many config knobs:** cpu_usage_mode, enable_parallel_processing, enable_raw_cache, enable_io_prefetch, batch_db_commits (most of these **unused in code**).
- **Staging:** Compress to `staging/` then copy to output (extra dir and cleanup).
- **Per-batch state files:** `state/batches/{id}.json` for “recent batches” in Tracker.
- **Folder browser + images-in-folder:** Full path picker, recursive, etc., for “choose folder” / “paste paths”.
- **Person UX:** Seed, add-reference, delete, thumbnails, “select which persons to search for”.

---

## 3. What’s essential vs. optional

### 3.1 Essential (must stay in some form)

- **Source and output paths** – where to read and write.
- **Person registry** – who to search for (names, output folders, embeddings/centroids).
- **Pipeline:** discover images → (optional: filter by selected paths/folder) → for each image: load/convert → detect faces → match → for matches: compress → write to each person’s folder.
- **Face stack:** InsightFace (or equivalent), matching with thresholds, optional learning.
- **RAW handling:** ARW → something usable for recognition and for delivery.
- **Some way to run it:** either “worker” process or “run in server”; at least one.
- **Some way to configure and start a job:** at least source, output, and “go”.
- **Deterministic filenames** – e.g. `stem__hash12.jpg` – to avoid overwrites and support idempotency in a simple form.

### 3.2 Useful but heavy (candidates to simplify)

- **Crash recovery / resume:** Full state machine + COMMITTING reconciliation + commit_log is heavy. A much simpler form: “we might re-run from start or from last known batch” with overwrite-safe filenames is enough for many use cases.
- **Atomic batches of 50:** Good for “how much can be lost” and for progress; the exact number and the full state machine could be reduced.
- **Staging directory:** Clear separation, but adds a step and cleanup. Could “compress straight to output” when it’s one person, or keep staging only when it really helps.
- **Tracker UI:** Nice for long runs; could be folded into Operator (single “status” section) or made optional.
- **“Select persons to search”:** Useful; could be “all” by default and “subset” as an opt-in to reduce UI and DB surface.
- **“Choose folder” / “paste paths”:** Useful; the current implementation (folder browser + images-in-folder + recursive) is heavier than a “source subfolder” or “text list” would need.

### 3.3 Likely removable or downgraded

- **Unused config:** `enable_raw_cache`, `raw_cache_max_size_gb`, `enable_io_prefetch`, `batch_db_commits` – defined but not used. Remove or implement; defining and ignoring adds confusion.
- **PathManager in `storage.paths`:** Imported in routing but not used; `StorageError` and `generate_deterministic_filename` are. Can drop `PathManager` or actually use it instead of ad‑hoc path checks.
- **Super-batch / “Super-Batch N”:** Extra concept for display; can be replaced by “Batch N” or “Image X–Y”.
- **Per-batch JSON in `state/batches/`:** Only for “recent batches” in Tracker. Could be replaced by a single “last_batch” or derived from `progress.json`.
- **Commit log’s full lifecycle:** `pending → written → verified` and `CommitReconciliation` are for “we crashed in the middle of copies.” Simpler: “we wrote this path” in one place, or rely on “file exists” + deterministic names.
- **`cpu_usage_mode` presets:** “adaptive/low/balanced/high/custom” could be “worker_count” (and maybe “auto” if we want one preset).

---

## 4. Duplication and split of responsibilities

- **Resume logic:** Implemented in both `batch_engine.run_resume_logic` and `worker.runner._resume_interrupted` (runner is the one actually used). One place is enough.
- **DB vs. state files:** Job config, batches, images, results, commit_log in DB; progress, batches, heartbeat in JSON. Largely consistent (DB = durable, JSON = UI) but the boundary could be simpler (e.g. “progress” could be DB or a single JSON, not progress + N batch files).
- **Engine vs. DB:** `batch_engine` drives everything and calls `jobs.*` and `registry.*`; `routing` uses `jobs.add_commit_entry`, `update_commit_status`, `check_output_exists_in_log`. The split is workable but there are a lot of small job/registry functions.

---

## 5. Proposed “minimal core” (target)

### 5.1 One-sentence architecture

> **One config (source, output, optional person filter, optional image list), one “run” that discovers (or uses a list) → processes in small chunks → writes matches; progress in one place (DB or one JSON); one UI to configure, run, and see status.**

### 5.2 Concretely

1. **Config (simplified)**  
   - Source path, output path.  
   - Optional: “only these persons” (default: all).  
   - Optional: “only these images” (list or “folder + recursive” or “all in source”).  
   - One “parallelism” knob: e.g. `worker_count` (plus maybe `auto`).

2. **Pipeline (simplified)**  
   - Discover (or take) image list; optional one-per-stem (jpg over arw) and path filters.  
   - Process in chunks (e.g. 50). No formal state machine: each chunk is “process all, then write all”. On crash: re-run skips already-written files (deterministic names) or we track “last completed chunk” in one place.  
   - No commit_log if we’re ok with “idempotency = same filename, skip if exists” or a single “written paths” list.  
   - Staging: keep only if we need “compress once, copy many”; otherwise consider “compress to output” when it’s one copy.

3. **DB (simplified)**  
   - **Keep:** persons, embeddings, centroids (registry).  
   - **Keep:** job_config (at least source, output; optional selected_*).  
   - **Keep:** jobs + images + batches for “what to do” and “what we’ve done” (or a much smaller equivalent).  
   - **Simplify or drop:** image_results if we only need “did we write this?” at the routing level; commit_log if we replace with “exists + deterministic name” or one simple log.  
   - One clear “progress” source: e.g. `processed_images` (and maybe `last_batch_id`) in `jobs` or one `progress.json`, not progress + N batch JSONs.

4. **State / tracker**  
   - One progress view: total, done, current chunk, ETA.  
   - Option A: Tracker = one section inside Operator.  
   - Option B: Keep Tracker page but feed it from one `progress.json` (no `state/batches/` or we derive “recent” from one structure).

5. **APIs (simplified)**  
   - **Operator:**  
     - get/set config (source, output, selected persons, selected images or “mode”).  
     - persons: list, add (seed), delete; “add reference” can stay.  
     - start / stop / job-status.  
     - If we keep “choose folder” / “paste paths”: one “list images under path” (with optional recursive) is enough; we can drop a separate “browse-folders” if we’re ok with typing a path or a simpler picker.  
   - **Tracker:**  
     - progress (from one source).  
     - worker-status (heartbeat) if we keep a separate worker process.

6. **Worker**  
   - One loop: read config → discover or take image list → process chunks → write.  
   - One place for “resume” (if we keep it): e.g. “reset PROCESSING→PENDING” and “finish COMMITTING” in `runner` only; remove from `batch_engine`.  
   - Heartbeat stays if we want worker-status.

7. **Config (code)**  
   - Remove or implement: `enable_raw_cache`, `enable_io_prefetch`, `batch_db_commits`.  
   - Consolidate: e.g. `worker_count` (+ `auto`) instead of five `cpu_usage_mode` values.  
   - Keep: paths, thresholds, batch_size, output quality/size, `supported_extensions`.

8. **Dead / underused**  
   - Drop `PathManager` or use it.  
   - Drop `run_resume_logic` from `batch_engine` if runner owns resume.  
   - Simplify or drop per-batch `state/batches/*.json` and the “recent batches” concept, or derive it from one structure.

---

## 6. What we are *not* changing (in this plan)

- Face model and matching logic (InsightFace, thresholds, learning).  
- RAW conversion and compression quality/size (we can tune later for speed).  
- External HDD discipline: read-only source, append-only output (no overwrites).  
- Person registry data model (persons, embeddings, centroids).  
- High-level flow: discover → process → write.

---

## 7. Order of work (suggested)

1. **Audit and trim config**  
   - Remove or stub unused: raw_cache, io_prefetch, batch_db_commits.  
   - Optionally replace `cpu_usage_mode` with `worker_count` (+ `auto`).

2. **Remove dead / duplicate code**  
   - PathManager in routing (and/or in `paths.py` if fully unused).  
   - `run_resume_logic` in `batch_engine` (keep only in `runner`).

3. **Simplify state for Tracker**  
   - One `progress.json` (or DB) as the source of truth.  
   - Drop or derive `state/batches/*.json` and “recent batches” from it.

4. **Simplify commit / idempotency**  
   - Decide: keep commit_log and reconciliation, or move to “deterministic name + exists check” and a much simpler “we wrote these” log.  
   - Then simplify `routing` and `jobs` accordingly.

5. **Simplify ingest and image selection**  
   - Keep “all / folder / paste” but with minimal API (e.g. one `images-in-folder` with `recursive`; folder browser only if we need it for “choose folder”).

6. **Optional: merge Tracker into Operator**  
   - One page: config, persons, run, and a “progress” block. Tracker becomes optional or a “full-screen progress” view.

7. **Then: speed**  
   - After the above, apply performance work: RAW (faster demosaic, smaller recognition size), face (smaller det size, optional GPU), batching DB writes, etc.

---

## 8. Open questions

1. **How crash-safe do you need?**  
   - “Re-run from start, skip existing” vs. “resume from last batch” vs. “full COMMITTING reconciliation.”

2. **Do you need two UIs?**  
   - One tab for “run” and one for “watch on another screen” vs. a single “Operator + status” page.

3. **Staging:**  
   - Keep (compress once, copy to N person folders) or allow “compress straight to output” when N=1?

4. **Commit log:**  
   - Keep for strong idempotency and recovery, or drop and rely on deterministic names + “exists”?

5. **Config:**  
   - Prefer fewer knobs (e.g. `worker_count` only) or keep “low/balanced/high” for non-expert users?

---

## 9. Summary

| Area           | Today                         | Target                                |
|----------------|-------------------------------|----------------------------------------|
| Config         | ~25 options, several unused   | Fewer, all used; e.g. `worker_count`   |
| State machine  | 4 states + reconciliation     | Chunks + simple resume or re-run       |
| State files    | progress + N batch JSONs      | One progress source                    |
| Commit log     | Full lifecycle + reconciler   | Simpler or “exists + names”            |
| Staging        | Always                        | Keep if fan-out; else optional         |
| Tracker        | Separate page + API           | One progress source; maybe in Operator |
| Resume         | In batch_engine and runner    | Only in runner                         |
| PathManager    | In paths, imported in routing | Use or remove                          |
| Image selection| browse + images-in-folder     | Keep minimal: folder + recursive       |

Next step: choose which of the “open questions” and target simplifications you want, then we can break that into concrete code edits (modules to change, functions to remove, and in what order).
