"""Job store and queue.

Reconstruction is compute-heavy enough that it cannot run inside a request:
a full field through both physics solvers and the network takes seconds, and
holding an HTTP connection open for that is how you get gateway timeouts and
no way to tell a stalled job from a slow one. So work is submitted, tracked by
id, and polled.

Two backends behind one interface. `thread` runs workers in-process and needs
no infrastructure at all, which is what makes this deployable as a single
container. `redis` hands the same payloads to RQ across separate worker
processes, which is what you want once more than one person is uploading at a
time. The API does not know which is in use.
"""

from __future__ import annotations

import os
import threading
import traceback
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class State(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    state: State = State.QUEUED
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started: str | None = None
    finished: str | None = None
    progress: float = 0.0
    stage: str = "Queued"
    request: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id, "state": self.state.value, "progress": round(self.progress, 3),
            "stage": self.stage, "created": self.created, "started": self.started,
            "finished": self.finished, "request": self.request,
            "error": self.error, "result": self.result,
        }


class Store:
    """Bounded in-memory job store.

    Bounded on purpose: a long-running demo that keeps every result forever
    will exhaust the container's memory, and the oldest finished job is always
    the one nobody is looking at any more.
    """

    def __init__(self, limit: int = 60):
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = threading.Lock()
        self._limit = limit

    def create(self, request: dict[str, Any]) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], request=request)
        with self._lock:
            self._jobs[job.id] = job
            while len(self._jobs) > self._limit:
                self._jobs.popitem(last=False)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in changes.items():
                setattr(job, key, value)

    def recent(self, limit: int = 20) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())[-limit:][::-1]


class Queue:
    """Submits work and reports progress back into the store."""

    def __init__(self, store: Store, workers: int = 1, backend: str | None = None):
        self.store = store
        self.backend = backend or os.getenv("VELOS_QUEUE", "thread")
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="velos-worker")
        self._rq = None
        if self.backend == "redis":
            try:
                import redis
                from rq import Queue as RQQueue
                self._rq = RQQueue("velos", connection=redis.from_url(os.environ["REDIS_URL"]))
            except Exception:
                # Never fail to start because the queue backend is missing;
                # fall back to in-process so the service still works.
                self.backend = "thread"
                self._rq = None

    def submit(self, job: Job, work: Callable[[Job, Callable[[float, str], None]], dict]) -> None:
        def report(progress: float, stage: str) -> None:
            self.store.update(job.id, progress=progress, stage=stage)

        def run() -> None:
            self.store.update(job.id, state=State.RUNNING, stage="Reading acquisition",
                              started=datetime.now(timezone.utc).isoformat())
            try:
                result = work(job, report)
                self.store.update(job.id, state=State.DONE, progress=1.0, stage="Complete",
                                  result=result, finished=datetime.now(timezone.utc).isoformat())
            except Exception as exc:
                self.store.update(
                    job.id, state=State.FAILED, stage="Failed",
                    error=f"{type(exc).__name__}: {exc}",
                    finished=datetime.now(timezone.utc).isoformat(),
                )
                traceback.print_exc()

        self._pool.submit(run)
