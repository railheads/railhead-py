from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Capability:
    tag:         str
    description: str
    status:      str
    category:    str = ""
    providers:   list[str] = field(default_factory=list)
    price_min:   float = 0.0
    price_max:   float = 0.0

    def __str__(self):
        providers = f"{len(self.providers)} provider(s)" if self.providers else "no providers yet"
        return f"[{self.status}] {self.tag} — {self.description[:60]}... ({providers})"


@dataclass
class Agent:
    address:        str
    capabilities:   list[str]
    price_rail:     float
    stake_rail:     float
    reputation:     int
    status:         str
    completed_jobs: int
    endpoint:       str

    def __str__(self):
        return (f"{self.address[:10]}...  caps={self.capabilities}  "
                f"stake={self.stake_rail:.0f} RAIL  jobs={self.completed_jobs}  rep={self.reputation}")


@dataclass
class Job:
    id:          int
    capability:  str
    client:      str
    agent:       str
    payment_rail: float
    status:      str
    tx_hash:     str = ""
    input:       dict = field(default_factory=dict)
    _chain:      Any  = field(default=None, repr=False)
    _api_url:    str  = field(default="", repr=False)

    # Job status codes from JobMarket.sol: Open, Accepted, Complete, Disputed, Cancelled, Expired
    _STATUS = {0: "Open", 1: "Accepted", 2: "Complete", 3: "Disputed", 4: "Cancelled", 5: "Expired"}

    def wait(self, timeout: int = 120, poll_secs: float = 3.0) -> "Result":
        """Block until the job is settled (or timeout). Returns the Result."""
        import time
        if self._chain is None:
            raise RuntimeError("Job has no chain reference — use client.post_job()")
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self._chain.job_market.functions.jobs(self.id).call()
            status_code = raw[10]
            if status_code == 2:  # Complete
                raw_r = self._chain.result_store.functions.results(self.id).call()
                output = {}
                if self._api_url:
                    try:
                        import requests
                        r = requests.get(f"{self._api_url}/job-results/{self.id}", timeout=8)
                        if r.ok:
                            output = r.json().get("result", {}) or {}
                    except Exception:
                        output = {}
                return Result(
                    job_id=self.id,
                    result_hash="0x" + raw_r[2].hex(),
                    status="Complete",
                    output=output,
                    mediator=raw_r[8],
                    note=raw_r[9],
                )
            if status_code in (3, 4, 5):
                return Result(job_id=self.id, status=self._STATUS.get(status_code, "Unknown"))
            time.sleep(poll_secs)
        raise TimeoutError(f"Job #{self.id} did not settle within {timeout}s")

    def __str__(self):
        return f"Job #{self.id} [{self.status}] {self.capability} — {self.payment_rail:.1f} RAIL"


@dataclass
class Result:
    job_id:      int
    status:      str = "Settled"
    result_hash: str = ""
    output:      dict = field(default_factory=dict)
    mediator:    str = ""
    note:        str = ""

    def __str__(self):
        return f"Result(job={self.job_id} status={self.status} note={self.note!r})"
