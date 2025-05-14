"""
Generate release notes from GitHub pull requests and tags.

This script automates the generation of release notes by:
1. Fetching all pull requests from a GitHub repository using pagination
2. Fetching Git tags and resolving each tag's commit date
3. Grouping PRs by Git tag intervals based on merge dates
   - If a PR was merged after the most recent tag's date, it goes into "Unreleased".
   - The "Unreleased" version number is automatically bumped from the last known tag version by +0.0.1
4. Generating formatted release notes with:
   - Table of contents
   - Version blocks
   - Categorized PRs with motivation sections

The script supports various command line arguments:
--token: GitHub Personal Access Token (default: GITHUB_TOKEN env var)
--owner: GitHub repository owner/org (required)
--repo: GitHub repository name (required)
--state: PR state to fetch (default: all)
--output: Output filename (default: stdout)
--per-page: PRs per GitHub API request (default: 100)
--max-pages: Max pages to fetch (default: 10)

The generated release notes are formatted in Markdown with:
- Version headers with dates
- PRs grouped by category (Features, Fixes, etc)
- PR titles, numbers and motivation sections
- Links to PRs

Example usage:
    python generate_release_notes.py --owner myorg --repo myrepo --token abc123

Example output (see `docs/release_notes.md` for the full output):

```markdown
# Release Notes

## v0.2.1 (2024-12-31)

### Features

- [FEAT] Implement ROS Task Executor Node with Navigation Example (#15)
  - **Motivation**: Add a task executor example for other vehicle modules to refer to.
```

Dependencies:
    - requests
    - packaging
    - python-dateutil
"""

import argparse
import os
import re
import sys
import requests
from packaging import version
from typing import List, Dict, Any, Optional

# -----------------------------------------------------------------------------
# 1) Argparse Setup
# -----------------------------------------------------------------------------

# Number of seconds to allow between PR merge time and tag commit time
# when determining which tag a PR belongs to
TIMESTAMP_TOLERANCE = 10


def parse_args() -> argparse.Namespace:
    """
    Parse and validate command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Generate release notes from GitHub pull requests and tags."
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub Personal Access Token (PAT). "
        "Default read from environment var GITHUB_TOKEN.",
    )
    parser.add_argument(
        "--owner",
        required=True,
        help="GitHub repository owner (org or username).",
    )
    parser.add_argument(
        "--repo", required=True, help="GitHub repository name."
    )
    parser.add_argument(
        "--state",
        default="all",
        choices=["open", "closed", "all"],
        help="Pull Request state to fetch. Default='all'.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output filename for the generated release notes. Default=None (stdout).",
    )
    parser.add_argument(
        "--per-page",
        default=100,
        type=int,
        help="Number of PRs per request to GitHub. Max=100. Default=100.",
    )
    parser.add_argument(
        "--max-pages",
        default=10,
        type=int,
        help="Max number of pages to fetch. Each page has up to --per-page items.",
    )
    return parser.parse_args()


# -----------------------------------------------------------------------------
# 2) GitHub API Helpers
# -----------------------------------------------------------------------------


def github_request(
    url: str, token: str, params: Dict[str, Any] = None
) -> requests.Response:
    """
    Make an authenticated GET request to the GitHub API.

    Args:
        url: GitHub API endpoint URL
        token: GitHub Personal Access Token
        params: Optional query parameters

    Returns:
        requests.Response: Response from GitHub API

    Raises:
        RuntimeError: If request fails with non-200 status code
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise RuntimeError(
            f"GitHub API request failed: {resp.status_code}\n{resp.text}"
        )
    return resp


def fetch_all_pull_requests(
    owner: str,
    repo: str,
    token: str,
    state: str = "all",
    per_page: int = 100,
    max_pages: int = 10,
) -> List[Dict[str, Any]]:
    """
    Fetch all pull requests from a GitHub repository using pagination.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        token: GitHub Personal Access Token
        state: PR state to fetch (open/closed/all)
        per_page: Number of PRs per page
        max_pages: Maximum number of pages to fetch

    Returns:
        List[Dict]: List of PR objects from GitHub API
    """
    all_prs = []
    base_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"

    page = 1
    while page <= max_pages:
        params = {
            "state": state,
            "per_page": per_page,
            "page": page,
            "direction": "asc",  # or 'desc'
        }
        print(f"Fetching PRs page={page} ...")
        resp = github_request(base_url, token, params=params)
        prs_batch = resp.json()
        if not prs_batch:
            break
        all_prs.extend(prs_batch)
        page += 1

    print(f"Total PRs fetched: {len(all_prs)}")
    return all_prs


def fetch_tags(
    owner: str, repo: str, token: str, per_page: int = 100, max_pages: int = 10
) -> List[Dict[str, Any]]:
    """
    Fetch all tags from a GitHub repository and their commit dates.

    Makes additional API calls to get commit dates for each tag.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        token: GitHub Personal Access Token
        per_page: Number of tags per page
        max_pages: Maximum number of pages to fetch

    Returns:
        List[Dict]: List of tag objects with:
            - name: Tag name
            - commit_date: ISO 8601 commit date
            - sha: Commit SHA
            - semver: packaging.version.Version object if tag is semver
    """
    tags_url = f"https://api.github.com/repos/{owner}/{repo}/tags"
    all_tags = []
    page = 1
    while page <= max_pages:
        params = {"per_page": per_page, "page": page}
        print(f"Fetching tags page={page} ...")
        resp = github_request(tags_url, token, params=params)
        tags_batch = resp.json()
        if not tags_batch:
            break

        # For each tag, fetch the commit date
        for tag_info in tags_batch:
            tag_name = tag_info.get("name", "")
            commit_sha = tag_info["commit"]["sha"]
            # We fetch commit details to get commit date
            commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}"
            commit_resp = github_request(commit_url, token)
            commit_data = commit_resp.json()
            commit_date = commit_data["commit"]["committer"][
                "date"
            ]  # e.g. "2021-05-28T14:34:55Z"

            # Attempt to parse semantic version from tag_name
            # May fail if tag_name is not valid semver, so fallback
            try:
                semver = version.Version(
                    tag_name.lstrip("v")
                )  # in case tags are like 'v0.2.3'
            except Exception:
                semver = None

            all_tags.append(
                {
                    "name": tag_name,
                    "commit_date": commit_date,
                    "sha": commit_sha,
                    "semver": semver,
                }
            )
        page += 1

    print(f"Total tags fetched: {len(all_tags)}")
    return all_tags


# -----------------------------------------------------------------------------
# 3) Data Processing Logic
# -----------------------------------------------------------------------------


def extract_motivation_section(body: str) -> str:
    """
    Extract the Motivation section from a PR description.

    Looks for text between "## Motivation" and the next "## " heading.

    Args:
        body: PR description text in Markdown

    Returns:
        str: Extracted motivation text or empty string if not found
    """
    if not body:
        return ""
    # Regex to find text after "## Motivation" until next "## " or the end
    pattern = re.compile(r"(?<=## Motivation)(.*?)(?=## )", re.DOTALL)
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def parse_iso_date(date_str: str):
    """
    Convert ISO 8601 datetime string to UTC timestamp.

    Args:
        date_str: ISO 8601 datetime string

    Returns:
        float: UTC timestamp
    """
    from datetime import timezone
    from dateutil import parser as dateparser

    # Parse the ISO string into a timezone-aware datetime
    dt = dateparser.parse(date_str)

    # Convert to UTC if timezone info exists
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)

    # Return UTC timestamp
    return dt.timestamp()


def sort_tags_by_commit_date(
    tags: List[Dict[str, Any]], ascending=False
) -> List[Dict[str, Any]]:
    """
    Sort tags by their commit date.

    Args:
        tags: List of tag objects with commit_date field
        ascending: Sort ascending if True, descending if False

    Returns:
        List[Dict]: Sorted list of tag objects
    """
    tags_sorted = sorted(
        tags,
        key=lambda t: parse_iso_date(t["commit_date"]),
        reverse=not ascending,
    )
    return tags_sorted


def determine_version_for_pr(
    merged_ts: float, sorted_tags_asc: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Find which version/tag a PR belongs to based on merge time.

    A PR belongs to the first tag that comes after its merge time.
    If merge time is within TIMESTAMP_TOLERANCE of a tag, PR belongs to that tag.

    Example:
        if PR merged at 2023-01-04 and we have tags:
            Tag A @ 2022-12-01
            Tag B @ 2023-01-05
            Tag C @ 2023-01-20
        Then the PR belongs to Tag B, because Tag B is the latest tag with a date later than 2023-01-04.

    Args:
        merged_ts: PR merge timestamp
        sorted_tags_asc: Tags sorted by date ascending

    Returns:
        Dict: Tag object the PR belongs to, or None if PR is older than all tags
    """
    selected_tag = None
    for idx, tag in enumerate(sorted_tags_asc):
        tag_ts = parse_iso_date(tag["commit_date"])
        # if the tag_ts is > merged_ts, this is the first tag after the PR merge
        if tag_ts > merged_ts:
            selected_tag = tag
            break
        # or if the tag_ts is within several seconds of merged_ts, we also select it
        elif abs(tag_ts - merged_ts) < TIMESTAMP_TOLERANCE:
            selected_tag = tag
            break
    return selected_tag


def bump_patch_version(semver: version.Version, bump_amount=1) -> str:
    """
    Increment the patch version number.

    Example:
        v0.2.3 -> v0.2.4

    Args:
        semver: Version object to bump
        bump_amount: Amount to increment patch by

    Returns:
        str: New version string with incremented patch number
    """
    major, minor, patch = semver.major, semver.minor, semver.micro
    patch += bump_amount
    return f"{major}.{minor}.{patch}"


# -----------------------------------------------------------------------------
# 4) Main Release Notes Generation
# -----------------------------------------------------------------------------


def main():
    """
    Main entry point for generating release notes.

    1. Parse command line args
    2. Fetch PRs and tags from GitHub
    3. Group PRs by version/tag
    4. Generate formatted release notes
    5. Write to file or stdout
    """
    args = parse_args()

    # Validate token
    if not args.token:
        sys.stderr.write(
            "Error: No GitHub token provided via --token or GITHUB_TOKEN env.\n"
        )
        sys.exit(1)

    # 4.1) Fetch All PRs (with pagination)
    all_prs = fetch_all_pull_requests(
        owner=args.owner,
        repo=args.repo,
        token=args.token,
        state=args.state,
        per_page=args.per_page,
        max_pages=args.max_pages,
    )

    # 4.2) Fetch All Tags & sort them by ascending commit date
    all_tags = fetch_tags(
        owner=args.owner,
        repo=args.repo,
        token=args.token,
        per_page=args.per_page,
        max_pages=args.max_pages,
    )
    # If no tags, we treat everything as "Unreleased" or an initial version.
    all_tags_sorted_asc = sort_tags_by_commit_date(all_tags, ascending=True)

    # 4.3) Build an index by tag_name -> list of PRs
    # We'll store them by the "tag dict" instead of just name to keep all info.
    # Then after we assign, we can build "version_buckets" for release notes.

    # For PR grouping, we need each PR's merged_at date. If not merged, we might treat it as "unreleased".
    # Or you might decide to skip unmerged PRs or use closed_at if it's closed unmerged.
    pr_by_tag = {}
    for t in all_tags_sorted_asc:
        pr_by_tag[t["name"]] = []

    # We'll also keep a separate "unreleased" bucket for PRs merged after the last tag
    unreleased = []
    no_merge_date = []  # For PRs that are open or never merged

    for pr in all_prs:
        merged_at = pr.get("merged_at")
        if merged_at is None:
            # not merged -> consider it "Unreleased" or skip
            no_merge_date.append(pr)
            continue

        merged_ts = parse_iso_date(merged_at)
        if not all_tags_sorted_asc:
            # No tags at all, everything is "Unreleased"
            unreleased.append(pr)
        else:
            # determine which tag this PR belongs to
            matched_tag = determine_version_for_pr(
                merged_ts, all_tags_sorted_asc
            )
            if matched_tag is None:
                # Check if PR is older than earliest tag or newer than latest tag
                earliest_tag_ts = parse_iso_date(
                    all_tags_sorted_asc[0]["commit_date"]
                )
                latest_tag_ts = parse_iso_date(
                    all_tags_sorted_asc[-1]["commit_date"]
                )

                if merged_ts < earliest_tag_ts:
                    # Case 1: PR is older than the earliest tag date
                    # Place it in the earliest version
                    earliest_tag_name = all_tags_sorted_asc[0]["name"]
                    pr_by_tag[earliest_tag_name].append(pr)
                elif merged_ts > latest_tag_ts:
                    # Case 2: PR is newer than the latest tag date
                    # Set it to unreleased
                    unreleased.append(pr)
                else:
                    # Log warning
                    print(
                        f"Warning: PR {pr['number']} is can't be assigned to any tag."
                    )
            else:
                # If matched_tag is not the last tag, that means there's a newer tag with a date after it
                # so it belongs to matched_tag
                # BUT if it's actually "older than the last tag date"?
                # That means matched_tag is that last tag.
                # If there's a tag date that's bigger than merged_ts, matched_tag won't advance beyond it.
                # This is correct.
                # We'll just append it to matched_tag's PR list.
                pr_by_tag[matched_tag["name"]].append(pr)

    # Now we should see if any PR is actually after the last tag's date
    if all_tags_sorted_asc:
        last_tag = all_tags_sorted_asc[-1]
        last_tag_ts = parse_iso_date(last_tag["commit_date"])
        # we'll handle only PRs that have a merged_at > last_tag_ts
        # but let's re-check the 'matched_tag' logic for them
        # Actually, if a PR is > last_tag_ts, matched_tag would be the last_tag, so it should end up in "unreleased" if we choose
        # but let's do an explicit pass:
        for pr in pr_by_tag[last_tag["name"]][
            :
        ]:  # copy list to avoid mutation issues
            merged_at = pr.get("merged_at")
            merged_ts = parse_iso_date(merged_at) if merged_at else 0
            if merged_ts > last_tag_ts + TIMESTAMP_TOLERANCE:
                # Move it to unreleased
                pr_by_tag[last_tag["name"]].remove(pr)
                unreleased.append(pr)

    # Also add open PRs or no_merge_date PRs to "unreleased" by default
    unreleased.extend(no_merge_date)

    # 4.4) Build final "version_buckets" in descending order by tag's semver or date
    #   e.g. v0.2.3, v0.2.2, v0.1.0, ...
    #   Then add "Unreleased" at the top if there's any PRs there.
    version_buckets = []
    # Sort tags in descending order by commit date
    all_tags_sorted_desc = sorted(
        all_tags_sorted_asc,
        key=lambda t: parse_iso_date(t["commit_date"]),
        reverse=True,
    )

    for tag in all_tags_sorted_desc:
        ver_str = tag["name"]

        # Add the date to the version label
        commit_date = tag["commit_date"][:10]  # Get YYYY-MM-DD part
        ver_label = f"{ver_str} ({commit_date})"

        # if it's something like "v0.2.3", keep it. Otherwise just use the raw name.
        # We also might want to handle semver conversion if tag["semver"] is not None
        version_buckets.append(
            {"version_label": ver_label, "pr_list": pr_by_tag[tag["name"]]}
        )

    # Construct an "Unreleased" version label. Possibly auto-bump from the last tag's semver.
    unreleased_ver_label = "Unreleased"
    if unreleased:
        if all_tags_sorted_desc and all_tags_sorted_desc[0].get("semver"):
            # Bump last tag
            last_semver = all_tags_sorted_desc[0]["semver"]
            new_semver_str = bump_patch_version(last_semver)
            unreleased_ver_label = f"v{new_semver_str} (Unreleased)"
        else:
            # No valid semver tags or no tags at all
            unreleased_ver_label = (
                "v0.0.1 (Unreleased)"  # if no tags found at all
            )

    # Insert Unreleased at the top
    version_buckets.insert(
        0, {"version_label": unreleased_ver_label, "pr_list": unreleased}
    )

    # -----------------------------------------------------------------------------
    # 4.5) Generate the release_notes.md
    # -----------------------------------------------------------------------------
    lines = []
    lines.append("---")
    lines.append("title: 版本发布日志")
    lines.append("---\n")
    lines.append("- [版本发布日志](#版本发布日志)")

    # Add each version to the Table of Contents
    for bucket in version_buckets:
        ver_label = bucket["version_label"]
        # Skip empty unreleased version
        if ver_label == "Unreleased" and not bucket["pr_list"]:
            continue

        # Generate an anchor (e.g., 'v0.2.4 (Unreleased)' -> 'v024-unreleased')
        anchor_text = (
            ver_label.lower()
            .replace("(", "")
            .replace(")", "")
            .replace(" ", "-")
            .replace(".", "")
        )
        lines.append(f"  - [{ver_label}](#{anchor_text})")

    lines.append("\n# 版本发布日志")
    lines.append("\n本文档记录了本项目的版本发布历史，与各版本与 PR 相对应。")
    lines.append(
        "\n对于更为详细的变更内容，请参考 [代码变更日志](./changelog.md)。"
    )
    lines.append(
        "\n对于未进行 PR 同步的代码平台，可参考本文档了解各 PR 的标题与动机。\n"
    )

    # For each version bucket
    for bucket in version_buckets:
        ver_label = bucket["version_label"]
        anchor_text = (
            ver_label.lower()
            .replace("(", "")
            .replace(")", "")
            .replace(" ", "-")
            .replace(".", "")
        )
        # Skip empty unreleased version
        if ver_label == "Unreleased" and not bucket["pr_list"]:
            continue

        # Add version header
        lines.append(f"## {ver_label}\n")
        if not bucket["pr_list"]:
            lines.append("_(No pull requests found)_\n")
            continue

        # Sort PRs by number ascending and categorize
        sorted_prs = sorted(
            bucket["pr_list"], key=lambda x: x["number"], reverse=False
        )

        # Initialize categories
        categories = {
            "Features": [],
            "Improvements": [],
            "Fixes": [],
            "Refactorings": [],
            "Tests": [],
            "Build & Deployment": [],
            "Documentation": [],
        }

        # Categorize PRs
        for pr in sorted_prs:
            num = pr["number"]
            title = pr["title"]
            motivation = (
                extract_motivation_section(pr.get("body", ""))
                or "无动机描述。"
            )
            pr_entry = f"- {title} (#{num})\n  - **Motivation**: {motivation}"

            if "[FEAT]" in title:
                categories["Features"].append(pr_entry)
            elif "[REFACTOR]" in title:
                categories["Refactorings"].append(pr_entry)
            elif "[FIX]" in title:
                categories["Fixes"].append(pr_entry)
            elif "[PERF]" in title:
                categories["Improvements"].append(pr_entry)
            elif "[DOCS]" in title:
                categories["Documentation"].append(pr_entry)
            elif "[TEST]" in title:
                categories["Tests"].append(pr_entry)
            elif "[BUILD]" in title or "[CI]" in title:
                categories["Build & Deployment"].append(pr_entry)
            else:
                categories["Features"].append(pr_entry)  # Default category

        # Write each category that has PRs
        for category_name, prs in categories.items():
            if prs:
                lines.append(f"**{category_name}**\n")
                lines.extend(prs)
                lines.append("")

    # Write out the file
    if args.output is None:
        print("\n".join(lines))
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"Release notes successfully written to {args.output}")


# -----------------------------------------------------------------------------
# 5) Entry Point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
