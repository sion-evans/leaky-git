#!/usr/bin/env python3

import sys
import argparse
import requests
import time

GITHUB_API_URL = "https://api.github.com"

api_requests = 0
max_requests = 0
bearer_token = None
verbose = False
include_forks = False

def get_args():
    parser = argparse.ArgumentParser(description="Leaky Git is a tool that enumerates GitHub repositories and scans the commit history of each accessible repository for exposed email addresses.")

    parser.add_argument(
        "--username",
        dest="username",
        type=str,
        help="GitHub username as a string"
    )

    parser.add_argument(
        "--max-requests",
        dest="max_requests",
        type=int,
        default=0,
        help="Maximum number of API requests (0 = unlimited)"
    )

    parser.add_argument(
        "--token",
        dest="token",
        type=str,
        default=None,
        help="Optional GitHub personal access token"
    )

    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enable verbose output"
    )

    parser.add_argument(
        "--include-forks",
        dest="include_forks",
        action="store_true",
        default=False,
        help="Scan forked repositories"
    )

    args = parser.parse_args()

    if args.username:
        username_input = args.username.strip()
    elif not sys.stdin.isatty():
        username_input = sys.stdin.read().strip()
    else:
        parser.error("No username provided via --username or stdin")

    if not username_input:
        parser.error("Username cannot be empty")

    return username_input, args.max_requests, args.token, args.verbose, args.include_forks


def safe_get(url, params=None, timeout=10):
    global api_requests, max_requests, bearer_token

    if max_requests and api_requests >= max_requests:
        if verbose:
            print(f"Reached maximum API requests limit ({max_requests})")
        return

    headers = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    api_requests += 1

    if response.status_code == 403:
        reset = response.headers.get("X-RateLimit-Reset")
        msg = "GitHub API returned 403"
        if reset:
            try:
                reset_ts = int(reset)
                now_ts = int(time.time())
                seconds_left = max(0, reset_ts - now_ts)
                minutes_left = seconds_left // 60
                msg += f" - rate limit resets in {minutes_left} minutes"
            except ValueError:
                msg += f" - rate limit reset at: {reset}"
        raise RuntimeError(msg)

    return response


def validate_user(username: str) -> dict:
    url = f"{GITHUB_API_URL}/users/{username}"
    response = safe_get(url, timeout=10)

    if response.status_code == 404:
        raise ValueError("User does not exist")
    elif response.status_code != 200:
        raise ValueError(f"GitHub API error: HTTP {response.status_code} ({url})")

    return response.json()


def get_public_repos(username: str, per_page: int = 100) -> list:
    repos = []
    page = 1

    while True:
        url = f"{GITHUB_API_URL}/users/{username}/repos"
        params = {"per_page": per_page, "page": page}
        response = safe_get(url, params=params, timeout=10)

        if response.status_code != 200:
            raise ValueError(f"Failed to fetch repositories: HTTP {response.status_code} ({url})")

        page_data = response.json()
        if not page_data:
            break

        repos.extend(page_data)
        if len(page_data) < per_page:
            break
        page += 1

    return repos


def get_all_commits(repo_full_name: str, per_page: int = 100) -> list:
    commits_info = []
    page = 1

    while True:
   
        url = f"{GITHUB_API_URL}/repos/{repo_full_name}/commits"
        params = {"per_page": per_page, "page": page}
        response = safe_get(url, params=params, timeout=10)

        if response is None:
            if verbose:
                print(f"[!] NoneType returned from response for {repo_full_name}")
            break

        if response.status_code == 409:
            try:
                body = response.json()
                if "Git Repository is empty" in body.get("message", ""):
                    break
            except ValueError:
                pass

        if response.status_code != 200:
            raise ValueError(f"Failed to fetch commits for {repo_full_name}: HTTP {response.status_code} ({url})")

        page_data = response.json()
        if not page_data:
            break

        for commit_data in page_data:
            commit = commit_data.get("commit", {})
            author = commit.get("author", {})
            committer = commit.get("committer", {})

            author_name = author.get("name")
            author_email = author.get("email")
            committer_name = committer.get("name")
            committer_email = committer.get("email")

            commits_info.append({
                "repo": repo_full_name,
                "author_name": author_name,
                "author_email": author_email,
                "committer_name": committer_name,
                "committer_email": committer_email,
            })

        if len(page_data) < per_page:
            break
        page += 1

    return commits_info


def main():
    global max_requests, bearer_token, verbose
    username, max_requests, bearer_token, verbose, include_forks = get_args()
    all_commit_data = []
    seen = set()

    try:
        user_data = validate_user(username)
        repos = get_public_repos(username)

        if verbose:
            print(f"Max requests limit: {max_requests if max_requests else 'unlimited'}")
            print(f"Using token: {'Yes' if bearer_token else 'No'}")
            print()
            print(f"Valid GitHub user: {user_data['login']}")
            print(f"Repositories found: {len(repos)}")
            print()

        for repo in repos:
            repo_name = repo["name"]
            full_name = repo["full_name"]
            html_url = repo.get("html_url")
            
            if not include_forks and repo["fork"] == True:
                if verbose:
                    print(f"Skipping fork: {repo_name} ({html_url})")
                    print()
                continue

            if verbose:
                print(f"Parsing: {repo_name} ({html_url})")

            try:
                all_commits = get_all_commits(full_name)
                if verbose:
                    print(f"Total commits fetched: {len(all_commits)}")
                    print()

                for commit_info in all_commits:
                    entries = [
                        (commit_info['author_name'], commit_info['author_email'], html_url),
                        (commit_info['committer_name'], commit_info['committer_email'], html_url)
                    ]

                    for name, email, repo_url in entries:
                        key = (name, email, repo_url)
                        if key in seen:
                            continue
                        seen.add(key)
                        all_commit_data.append({
                            "name": name,
                            "email": email,
                            "repo_url": repo_url
                        })

            except RuntimeError as e:
                print(f"{e}")
            except ValueError as e:
                print(f"{e}")

        for entry in all_commit_data:
            if entry['name'] == "GitHub" and entry['email'] == "noreply@github.com":
                continue
            print(f"{entry['name']} <{entry['email']}> ({entry['repo_url']})")

        if verbose:
            print()
            print(f"Total unique entries: {len(all_commit_data)}")
            print(f"Total API requests made: {api_requests}")

    except RuntimeError as e:
        print(f"{e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
