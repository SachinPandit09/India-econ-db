"""Backfill runner: count -> fetch (archived) -> normalise -> load, with progress, resume and a circuit breaker.

One ops.source_run per dataset; a failing dataset never stops the others. Sessions run as econdb_writer.
"""

import math
import sys
import time
from collections import defaultdict
from datetime import date

from econdb import archive, db, http, log
from econdb.sources import mospi

PAUSE_AFTER = 10  # consecutive failed chunks pause a dataset (resumable by re-running the stage)
SECONDS_PER_PAGE = 1.4  # measured: ~0.3-1.1 s response + 0.6 s spacing


class Progress:
    def __init__(self, stage: str, chunks: int, pages: int):
        self.stage, self.chunks, self.pages = stage, chunks, max(pages, 1)
        self.chunks_done = self.pages_done = self.rows = 0
        self.dataset = ""
        self.t0 = time.monotonic()

    def page(self, page: int, pages: int, rows: int) -> None:
        self.pages_done += 1
        self.rows += rows
        elapsed = max(time.monotonic() - self.t0, 1e-6)
        rate = self.pages_done / elapsed * 60
        left = max(self.pages - self.pages_done, 0) / max(rate / 60, 1e-6)
        eta = f"{int(left // 3600)}h{int(left % 3600 // 60):02d}m"
        sys.stderr.write(
            f"\rstage {self.stage} | {self.dataset} | chunks {self.chunks_done}/{self.chunks} | "
            f"pages {self.pages_done}/{self.pages} | rows {self.rows:,} | {rate:.1f} req/min | ETA {eta}   "
        )
        sys.stderr.flush()


def estimate(chunks) -> dict[str, int | None]:
    """totalRecords per chunk (one small request each)."""
    totals = {}
    for i, ch in enumerate(chunks, 1):
        try:
            totals[ch.key] = mospi.count(ch)
        except http.HTTPFailure:
            totals[ch.key] = None
        sys.stderr.write(f"\rcounting rows: {i}/{len(chunks)} chunks   ")
    sys.stderr.write("\n")
    return totals


def archived_runs(ch) -> list[list[str]]:
    """Archived pages of a chunk grouped per fetch run, oldest run first."""
    marker = f"_{mospi.safe_key(ch.key)}_p"
    groups = defaultdict(list)
    for path in archive.files(f"mospi/{ch.dataset}"):
        name = path.rsplit("/", 1)[-1]
        if marker in name:
            groups[(path.split("/")[2], int(name.split("_", 1)[0].lstrip("r")))].append(path)
    return [groups[k] for k in sorted(groups)]


def load_pages(conn, ch, pages, source_run_id, logger) -> tuple[int, int, date | None, int]:
    batch = mospi.normalise(ch, pages)
    if batch.bad_rows:
        db.quality_issue(conn, source_run_id, "row_skipped", "warn",
                         {"chunk": ch.key, "count": len(batch.bad_rows), "samples": batch.bad_rows[:5]})  # fmt: skip
    loads, kept_raw = {}, []
    for target, rows in (("obs", batch.obs), ("cpi", batch.cpi), ("detail", batch.detail)):
        rows, conflicts, ambiguous = mospi.dedupe(rows, target)
        if conflicts:
            if target == "obs" and batch.detail:  # dataset already keeps every source row in raw
                extra = []
            else:
                extra = mospi.ambiguous_detail(target, ambiguous, batch.series)
            kept_raw += extra
            db.quality_issue(conn, source_run_id, "ambiguous_source_rows", "warn",
                             {"chunk": ch.key, "target": target, "keys": [str(k) for k in conflicts[:20]],
                              "rows": len(ambiguous), "kept_in_raw_mospi_detail": len(extra)})  # fmt: skip
        loads[target] = rows
    loads["detail"] = loads["detail"] + kept_raw
    with conn.transaction():
        discovered = db.add_series(conn, batch.series.values())
        counts = {t: db.load(conn, t, rows, source_run_id) for t, rows in loads.items()}
    latest = max((r[2] for r in loads["obs"]), default=None)
    logger.info("chunk loaded", fields={"chunk": ch.key, "rows_in": batch.rows_in, "discovered_series": discovered,
                                        **{f"{t}_new": c[0] for t, c in counts.items()},
                                        **{f"{t}_revised": c[1] for t, c in counts.items()}})  # fmt: skip
    return (
        sum(c[0] for c in counts.values()),
        sum(c[1] for c in counts.values()),
        latest,
        batch.rows_in,
    )


def run_chunk(
    conn, ch, run_id, source_run_id, from_archive, progress, logger, total
) -> tuple[int, int, date | None]:
    if from_archive:
        groups = [
            [(ref, *mospi.parse(archive.load(ref), ch.key)) for ref in refs]
            for refs in archived_runs(ch)
        ]
    else:
        groups = [list(mospi.fetch(ch, f"r{run_id}", on_page=progress.page))]
    new = revised = 0
    latest = None
    for pages in groups:
        n, r, lp, rows_in = load_pages(conn, ch, pages, source_run_id, logger)
        new, revised, latest = new + n, revised + r, max(filter(None, (latest, lp)), default=None)
        if not from_archive:
            db.mark_chunk(
                conn, "mospi", ch.dataset, ch.key, total, len(pages), rows_in, source_run_id
            )
            if total is not None and rows_in != total:
                db.quality_issue(conn, source_run_id, "row_count_mismatch", "warn",
                                 {"chunk": ch.key, "api_total": total, "fetched": rows_in})  # fmt: skip
    return new, revised, latest


def backfill(
    stage: str, datasets=None, refresh=False, from_archive=False, counts_only=False
) -> int:
    chunks = mospi.stage_chunks(stage, datasets)
    with db.connect() as conn:
        conn.autocommit = True
        if counts_only:
            return report_estimate(chunks, estimate(chunks))
        conn.execute("SET ROLE econdb_writer")
        mode = "from-archive" if from_archive else "refresh" if refresh else "resume"
        run_id = db.start_run(
            conn, f"backfill mospi stage={stage} datasets={datasets or '-'} {mode}", "backfill"
        )
        logger, log_path = log.setup(run_id)
        done = set() if refresh or from_archive else db.completed_chunks(conn, "mospi")
        todo = [ch for ch in chunks if ch.key not in done]
        print(
            f"run {run_id} | stage {stage} | {len(todo)} of {len(chunks)} chunks to do | log {log_path}"
        )
        totals = {} if from_archive else estimate(todo)
        pages = sum(math.ceil((totals.get(ch.key) or 1) / mospi.PAGE) for ch in todo)
        if not from_archive:
            print(f"about {sum(t or 0 for t in totals.values()):,} rows, {pages:,} pages, "
                  f"~{pages * SECONDS_PER_PAGE / 3600:.1f} h")  # fmt: skip
        progress = Progress(stage, len(todo), pages)
        by_dataset = defaultdict(list)
        for ch in todo:
            by_dataset[ch.dataset].append(ch)
        failed, status, source_run_id = [], "ok", None
        try:
            for dataset, items in by_dataset.items():
                progress.dataset = dataset
                source_run_id = db.start_source_run(conn, run_id, "mospi", dataset)
                new = revised = streak = 0
                latest, errors, paused = None, [], False
                for ch in items:
                    try:
                        n, r, lp = run_chunk(conn, ch, run_id, source_run_id, from_archive, progress, logger,
                                             totals.get(ch.key))  # fmt: skip
                        new, revised, streak = new + n, revised + r, 0
                        latest = max(filter(None, (latest, lp)), default=None)
                    except (http.HTTPFailure, ValueError, KeyError) as e:
                        streak += 1
                        failed.append((ch, source_run_id))
                        errors.append(f"{ch.key}: {e}")
                        logger.error("chunk failed", fields={"chunk": ch.key, "error": str(e)})
                        db.quality_issue(
                            conn,
                            source_run_id,
                            "chunk_failed",
                            "error",
                            {"chunk": ch.key, "error": str(e)},
                        )
                        if streak >= PAUSE_AFTER:
                            paused = True
                            logger.error(
                                "dataset paused", fields={"dataset": dataset, "after": streak}
                            )
                            break
                    progress.chunks_done += 1
                ds_status = "paused" if paused else "partial" if errors else "ok"
                status = "partial" if errors else status
                db.finish_source_run(conn, source_run_id, ds_status, new, revised, latest,
                                     "; ".join(errors)[:4000] or None)  # fmt: skip
                sys.stderr.write("\n")
                print(
                    f"{dataset:<12} {ds_status:<8} new {new:>9,}  revised {revised:>7,}  failed chunks {len(errors)}"
                )
            if (
                failed and not from_archive
            ):  # one more try at the end (e.g. PLFS indicator 5, HTTP 500)
                print(f"retrying {len(failed)} failed chunk(s) once")
                for ch, srid in failed:
                    try:
                        n, r, _ = run_chunk(
                            conn, ch, run_id, srid, False, progress, logger, totals.get(ch.key)
                        )
                        logger.info("retry ok", fields={"chunk": ch.key, "new": n})
                        print(f"  {ch.key}: ok on retry ({n:,} new)")
                    except (http.HTTPFailure, ValueError, KeyError) as e:
                        print(f"  {ch.key}: still failing - {e}")
        except KeyboardInterrupt:
            status = "partial"
            if source_run_id:
                db.finish_source_run(
                    conn, source_run_id, "paused", 0, 0, None, "interrupted (Ctrl+C)"
                )
            print("\ninterrupted - re-run the same command to resume from the last completed chunk")
        mismatch_report(conn, datasets or mospi.STAGES[stage], run_id)
        db.finish_run(conn, run_id, status)
        print(f"run {run_id} finished: {status} | log {log_path}")
    return 0 if status == "ok" else 1


META_DATASET = {
    "CPI2024": "CPI",
    "CPI2024BACK": "CPI",
    "CPI2012": "CPI",
    "CPI2012ITEM": "CPI",
    "CPI2010": "CPI",
}
STOP_WORDS = {"and", "of", "the", "in", "for", "a", "index", "value", "current", "prices"}


def mismatch_report(conn, datasets, run_id) -> None:
    """Layout-mapped series still without observations, each with the closest discovered series
    (same family + base, same frequency) by label-word overlap. Printed and saved as CSV."""
    import csv

    names = sorted({META_DATASET.get(d, d) for d in datasets})
    missing = conn.execute(
        """SELECT c.sheet_code, c.block_title, c.column_label, s.series_id
           FROM meta.sheet_column c JOIN meta.series s USING (series_id)
           WHERE s.derivation IS NULL AND s.dataset = ANY(%s)
             AND NOT EXISTS (SELECT 1 FROM core.observation o WHERE o.series_id = s.series_id)
           ORDER BY 1, 2, 3""",
        (names,),
    ).fetchall()
    found = conn.execute(
        """SELECT s.series_id, s.name FROM meta.series s WHERE s.dataset = ANY(%s)
             AND NOT EXISTS (SELECT 1 FROM meta.sheet_column c WHERE c.series_id = s.series_id)""",
        (names,),
    ).fetchall()
    pools = defaultdict(list)
    for sid, name in found:
        pools[(".".join(sid.split(".")[:2]), sid[-1])].append((sid, set(mospi.key(name).split())))
    rows = []
    for sheet, block, label, sid in missing:
        words = set(mospi.key(label).split()) - STOP_WORDS or set(mospi.key(label).split())
        pool = pools[(".".join(sid.split(".")[:2]), sid[-1])]
        score, best = max(((len(words & w) / len(words), d) for d, w in pool), default=(0.0, ""))
        rows.append((sheet, block, label, sid, best if score >= 0.5 else "", round(score, 2)))
    path = archive.root().parent / f"mismatch_run{run_id}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["sheet", "block", "column", "layout_series_id", "closest_discovered", "score"]
        )
        writer.writerows(rows)
    close = sum(1 for r in rows if r[4])
    print(
        f"mismatch report: {len(rows)} layout series without data ({close} with a close discovered match) -> {path}"
    )
    for r in rows[:15]:
        print(f"  {r[0]} {r[2][:34]:<34} {r[3]:<48} ~ {r[4] or '-'} ({r[5]})")


def report_estimate(chunks, totals) -> int:
    per = defaultdict(lambda: [0, 0, 0])
    for ch in chunks:
        t = totals.get(ch.key) or 0
        per[ch.dataset][0] += 1
        per[ch.dataset][1] += t
        per[ch.dataset][2] += max(1, math.ceil(t / mospi.PAGE))
    print(f"{'dataset':<12} {'chunks':>6} {'rows':>11} {'requests':>9} {'hours':>6}")
    for d, (n, rows, req) in per.items():
        print(f"{d:<12} {n:>6} {rows:>11,} {req:>9,} {req * SECONDS_PER_PAGE / 3600:>6.1f}")
    rows, req = sum(v[1] for v in per.values()), sum(v[2] for v in per.values())
    print(
        f"{'total':<12} {len(chunks):>6} {rows:>11,} {req:>9,} {req * SECONDS_PER_PAGE / 3600:>6.1f}"
    )
    return 0
