#!/usr/bin/env python3
# python3 gh_experiment.py --reps 50 --seed 42 --out-jsonl results.jsonl --out-csv results.csv

import os
import json
import csv
import time
import random
import argparse
import requests
from dotenv import load_dotenv
from typing import Dict, Any, List, Tuple

# ======================================================================
# LOAD TOKEN
# ======================================================================
load_dotenv()
TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing GITHUB_TOKEN in .env")

HEADERS_REST = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
    "Accept-Encoding": ""  # disable compression
}

HEADERS_GRAPHQL = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept-Encoding": ""  # disable compression
}

# ======================================================================
# EXPERIMENT OBJECTS
# ======================================================================
USERS = ["torvalds", "octocat", "defunkt", "mojombo", "pjhyett"]
REPOS = ["torvalds/linux", "octocat/Hello-World", "psf/requests", "django/django", "numpy/numpy"]

# ======================================================================
# GRAPHQL QUERIES (DESENHO DO EXPERIMENTO)
# ======================================================================
GQL_USER = """
query($login:String!) {
  user(login:$login) {
    login
    id
    name
    followers { totalCount }
  }
}
"""

GQL_REPO = """
query($owner:String!, $name:String!) {
  repository(owner:$owner, name:$name) {
    name
    description
    owner { login }
    stargazerCount
    forkCount
    licenseInfo { name }
  }
}
"""

GQL_ISSUES = """
query($owner:String!, $name:String!) {
  repository(owner:$owner, name:$name) {
    issues(first:50, orderBy:{field:CREATED_AT,direction:DESC}) {
      nodes {
        number
        title
        author { login }
        labels(first:10) { nodes { name } }
      }
    }
  }
}
"""

GRAPHQL_TASKS = {
    "simple_user": GQL_USER,
    "medium_repo": GQL_REPO,
    "complex_issues": GQL_ISSUES,
}

# ======================================================================
# REST ENDPOINTS (CAMPOS MAPEADOS EQUIVALENTEMENTE)
# ======================================================================

def rest_user(login: str) -> List[str]:
    """1 chamada REST."""
    return [f"https://api.github.com/users/{login}"]

def rest_repo(full: str) -> List[str]:
    """1 chamada REST."""
    return [f"https://api.github.com/repos/{full}"]

def rest_issues(full: str) -> List[str]:
    """
    Para 50 issues:
      - GitHub REST retorna no máximo 100 por página → OK em 1 chamada
    """
    return [f"https://api.github.com/repos/{full}/issues?per_page=50&state=all&sort=created&direction=desc"]

REST_TASKS = {
    "simple_user": rest_user,
    "medium_repo": rest_repo,
    "complex_issues": rest_issues,
}

# ======================================================================
# GENERIC REQUEST MEASUREMENT
# ======================================================================
def measure(method: str, url: str, json_body=None) -> Dict[str, Any]:
    t0 = time.time()

    try:
        if method == "GET":
            resp = requests.get(url, headers=HEADERS_REST, timeout=20)
        else:
            resp = requests.post(url, headers=HEADERS_GRAPHQL, json=json_body, timeout=20)

        dt = (time.time() - t0) * 1000
        return dict(
            status=resp.status_code,
            time_ms=dt,
            bytes=len(resp.content),
            error=None,
            rate_remaining = resp.headers.get("X-RateLimit-Remaining"),
            rate_reset = resp.headers.get("X-RateLimit-Reset"),
        )

    except Exception as e:
        return dict(
            status=None,
            time_ms=None,
            bytes=None,
            error=str(e),
            rate_remaining = None,
            rate_reset = None,
        )

# ======================================================================
# TASK EXECUTION
# ======================================================================
def run_graphql(task_name: str, params: Dict[str, Any]):
    query = GRAPHQL_TASKS[task_name]
    return dict(
        task=task_name,
        api="graphql",
        **params,
        **measure(
            "POST",
            "https://api.github.com/graphql",
            json_body={"query": query, "variables": params}
        ),
        rest_calls=0
    )

def run_rest(task_name: str, params: Dict[str, Any]):
    # Normalização: REST recebe apenas os parâmetros que realmente usa
    if task_name in ("medium_repo", "complex_issues"):
        clean_params = {"full": params["full"]}
    elif task_name == "simple_user":
        clean_params = {"login": params["login"]}
    else:
        raise RuntimeError(f"Unknown task_name: {task_name}")

    urls = REST_TASKS[task_name](**clean_params)

    total_time = 0
    total_bytes = 0
    final_status = 200
    error = None

    for url in urls:
        r = measure("GET", url)
        if r["status"] is None or not (200 <= r["status"] < 300):
            final_status = r["status"]
            error = r["error"]
        total_time += (r["time_ms"] or 0)
        total_bytes += (r["bytes"] or 0)

    return dict(
        task=task_name,
        api="rest",
        **params,           # ← mantém os parâmetros originais para registro
        status=final_status,
        time_ms=total_time,
        bytes=total_bytes,
        error=error,
        rest_calls=len(urls),
    )

# ======================================================================
# EXPERIMENT EXECUTION
# ======================================================================
def build_task_list():
    tasks = []
    for u in USERS:
        tasks.append(("simple_user", {"login": u}))

    for r in REPOS:
        owner, name = r.split("/")
        tasks.append(("medium_repo", {"owner": owner, "name": name, "full": r}))
        tasks.append(("complex_issues", {"owner": owner, "name": name, "full": r}))

    return tasks


def run_experiment(reps: int, warmup: int, seed: int,
                   out_jsonl: str, out_csv: str,
                   interval_min: int, interval_max: int):

    random.seed(seed)

    all_tasks = build_task_list()

    # Expand REST + GraphQL
    expanded = []
    for tname, params in all_tasks:
        base = dict(params)
        if "full" in base:
            base_rest = dict(full=base["full"])
        expanded.append(("graphql", tname, params))
        expanded.append(("rest", tname, params))

    random.shuffle(expanded)

    # Warm-up
    for _ in range(warmup):
        api, name, params = random.choice(expanded)
        if api == "graphql":
            run_graphql(name, params)
        else:
            run_rest(name, params)

    rows = []
    print("Experiment start:", time.strftime("%Y-%m-%d %H:%M:%S"))

    for _ in range(reps):
        for api, name, params in expanded:
            time.sleep(random.uniform(interval_min/1000, interval_max/1000))
            if api == "graphql":
                rows.append(run_graphql(name, params))
            else:
                rows.append(run_rest(name, params))

    # WRITE JSONL
    os.makedirs("output", exist_ok=True)
    with open(f"output/{out_jsonl}", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # WRITE CSV
    fields = sorted({k for r in rows for k in r.keys()})
    with open(f"output/{out_csv}", "w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print("Experiment end:", time.strftime("%Y-%m-%d %H:%M:%S"))

# ==========================================================
# 8. CLI
# ==========================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub API Experiment")
    parser.add_argument("--reps", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-jsonl", type=str, default="results.jsonl")
    parser.add_argument("--out-csv", type=str, default="results.csv")
    parser.add_argument("--interval-min", type=int, default=100)
    parser.add_argument("--interval-max", type=int, default=300)

    args = parser.parse_args()

    run_experiment(
        reps=args.reps,
        warmup=args.warmup,
        seed=args.seed,
        out_jsonl=args.out_jsonl,
        out_csv=args.out_csv,
        interval_min=args.interval_min,
        interval_max=args.interval_max
    )
