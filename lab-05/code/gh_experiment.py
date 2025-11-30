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
from typing import Dict, Any, List

# ==========================================================
# 1. Carregar TOKEN do .env
# ==========================================================
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise RuntimeError("ERRO: GITHUB_TOKEN não encontrado no arquivo .env")

OUTPUT_DIR = "output"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ==========================================================
# 2. Objetos experimentais (definidos conforme o desenho)
# ==========================================================
DEFAULT_USERS = ["torvalds", "octocat", "defunkt", "mojombo", "pjhyett"]
DEFAULT_REPOS = ["torvalds/linux", "octocat/Hello-World", "psf/requests", "django/django", "numpy/numpy"]

# ==========================================================
# 3. Consultas GraphQL
# ==========================================================
GRAPHQL_QUERIES = {
    "user_basic": """
        query($login: String!) {
            user(login: $login) {
                name
                login
                id
            }
        }
    """,
    "repo_basic": """
        query($owner: String!, $name: String!) {
            repository(owner: $owner, name: $name) {
                name
                id
                stargazerCount
                forkCount
            }
        }
    """,
    "repo_issues": """
        query($owner: String!, $name: String!) {
            repository(owner: $owner, name: $name) {
                issues(first: 10) {
                    nodes { id title state }
                }
            }
        }
    """,
    "repo_commits": """
        query($owner: String!, $name: String!) {
            repository(owner: $owner, name: $name) {
                defaultBranchRef {
                    target {
                        ... on Commit {
                            history(first: 10) {
                                edges { node { oid messageHeadline author { name } } }
                            }
                        }
                    }
                }
            }
        }
    """,
}

# ==========================================================
# 4. Endpoints REST equivalentes
# ==========================================================
REST_ENDPOINTS = {
    "user_basic": lambda login: f"https://api.github.com/users/{login}",
    "repo_basic": lambda full: f"https://api.github.com/repos/{full}",
    "repo_issues": lambda full: f"https://api.github.com/repos/{full}/issues?per_page=10&state=all",
    "repo_commits": lambda full: f"https://api.github.com/repos/{full}/commits?per_page=10",
}

# ==========================================================
# 5. Função de medição
# ==========================================================
def measure_request(method: str, url: str = None, json_body: Dict = None,
                    headers: Dict = None, timeout: float = 20.0) -> Dict[str, Any]:

    t0 = time.time()

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=timeout)
        else:
            resp = requests.post(url, json=json_body, headers=headers, timeout=timeout)

        t1 = time.time()

        return {
            "status": resp.status_code,
            "time_ms": (t1 - t0) * 1000,
            "bytes": len(resp.content),
            "rate_remaining": resp.headers.get("X-RateLimit-Remaining"),
            "rate_reset": resp.headers.get("X-RateLimit-Reset"),
            "error": None,
        }

    except Exception as e:
        return {
            "status": None,
            "time_ms": None,
            "bytes": None,
            "rate_remaining": None,
            "rate_reset": None,
            "error": str(e),
        }

# ==========================================================
# 6. Execução de uma tarefa (REST ou GraphQL)
# ==========================================================
def execute_task(task, headers_graphql, headers_rest):
    name, typ, params = task

    if typ == "graphql":
        query = GRAPHQL_QUERIES[name]
        return {
            "task": name,
            "type": "graphql",
            **params,
            **measure_request(
                "POST",
                url="https://api.github.com/graphql",
                json_body={"query": query, "variables": params},
                headers=headers_graphql
            )
        }

    else:
        url = REST_ENDPOINTS[name](params.get("login") or params.get("full"))
        return {
            "task": name,
            "type": "rest",
            **params,
            **measure_request(
                "GET",
                url=url,
                headers=headers_rest
            )
        }

# ==========================================================
# 7. Execução completa do experimento
# ==========================================================
def run_experiment(reps: int, warmup: int, seed: int,
                   out_jsonl: str, out_csv: str,
                   interval_min: int, interval_max: int):

    random.seed(seed)

    out_jsonl = os.path.join(OUTPUT_DIR, out_jsonl)
    out_csv = os.path.join(OUTPUT_DIR, out_csv)

    headers_graphql = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept-Encoding": ""   # sem compressão
    }

    headers_rest = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Accept-Encoding": ""   # sem compressão
    }

    # Monta lista de tarefas
    tasks = []

    for login in DEFAULT_USERS:
        tasks.append(("user_basic", "graphql", {"login": login}))
        tasks.append(("user_basic", "rest", {"login": login}))

    for repo in DEFAULT_REPOS:
        owner, name = repo.split("/")
        tasks.append(("repo_basic", "graphql", {"owner": owner, "name": name}))
        tasks.append(("repo_basic", "rest", {"full": repo}))

        tasks.append(("repo_issues", "graphql", {"owner": owner, "name": name}))
        tasks.append(("repo_issues", "rest", {"full": repo}))

        tasks.append(("repo_commits", "graphql", {"owner": owner, "name": name}))
        tasks.append(("repo_commits", "rest", {"full": repo}))

    random.shuffle(tasks)

    # WARM-UP
    for _ in range(warmup):
        task = random.choice(tasks)
        execute_task(task, headers_graphql, headers_rest)

    # Execução principal
    rows = []

    print("Iniciando experimento as: " + time.strftime("%Y-%m-%d %H:%M:%S"))

    for _ in range(reps):
        for task in tasks:
            time.sleep(random.uniform(interval_min/1000, interval_max/1000))
            result = execute_task(task, headers_graphql, headers_rest)
            rows.append(result)

    # Salvar JSONL
    with open(out_jsonl, "w", encoding="utf-8") as jf:
        for r in rows:
            jf.write(json.dumps(r) + "\n")

    # Salvar CSV
    with open(out_csv, "w", encoding="utf-8", newline="") as cf:
        all_fields = set()
        for r in rows:
            all_fields.update(r.keys())
        all_fields = list(all_fields)

        writer = csv.DictWriter(cf, fieldnames=all_fields)
        writer.writeheader()

        # Preencher valores ausentes com vazio
        for r in rows:
            writer.writerow({field: r.get(field, "") for field in all_fields})

    print("Experimento concluído as: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"JSONL salvo em {out_jsonl}")
    print(f"CSV salvo em {out_csv}")

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
