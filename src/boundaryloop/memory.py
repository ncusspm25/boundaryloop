"""Local suggestions and small-sample statistics; neither grants authority."""

from __future__ import annotations

from .state import Store


def remember(store: Store, fp: str, attempt: dict, success: bool = False) -> None:
    matches = {item["fingerprint"]: item for item in store.all("memory")}
    item = matches.get(
        fp,
        {
            "fingerprint": fp,
            "recurrence_count": 0,
            "prior_attempts": [],
            "failed_strategies": [],
            "successful_strategies": [],
            "applicable_conditions": "Same validator, code area and environment; "
            "similarity does not establish a shared root cause",
        },
    )
    item["recurrence_count"] += 1
    item["prior_attempts"].append(attempt)
    key = "successful_strategies" if success else "failed_strategies"
    item[key].append(attempt.get("strategy", "unspecified"))
    store.put("memory", fp, item)


def record_profile(store: Store, run: dict) -> None:
    for receipt in run["receipts"]:
        # One observation per verified attempt, idempotently upserted; no claimed successes.
        observation = {
            "run_id": run["run_id"],
            "model": receipt["worker_model"],
            "category": run.get("category", "code-modification"),
            "verified_success": receipt["FINAL_STATUS"] == "PASS",
            "verified_failure": receipt["VALIDATOR_OBSERVED_STATUS"] == "FAIL",
            "retries": max(0, receipt["attempt"] - 1),
            "escalations": len(run["tickets"]),
            "seconds": receipt["execution_seconds"],
            "cost": None,
            "uncertainty": "Descriptive sample only; no capability guarantee",
        }
        store.put("profile", run["run_id"] + ":" + str(receipt["attempt"]), observation)
