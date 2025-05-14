"""Changelog PR marker extraction tool.

This script extracts changelog entries from a Markdown file that reference a specific PR marker.
It preserves the hierarchical bullet point structure while removing the PR marker references.

Example:
    Extract all changelog entries referencing PR #31:
    $ python collect_changelog.py changelog.md 31

    This will output all bullet points and their sub-bullets that contain '#31',
    with the '#31' marker removed from the output.

The script handles:
- Top-level bullet points starting with '- '
- Sub-bullet points indented with 2+ spaces
- Continuation lines that are part of bullet points
- Preservation of blank lines and formatting
- Removal of PR markers while keeping the rest of the text intact

The output maintains the original Markdown formatting for easy copy-pasting.
"""

import argparse
import re
from pathlib import Path
from typing import List


def extract_pr_changes(lines: List[str], pr_marker: str) -> List[str]:
    """Extract changelog entries referencing a specific PR marker.

    Processes a list of Markdown lines and extracts complete bullet point entries
    (including all sub-bullets and continuation lines) that reference the given PR marker.
    The PR marker is removed from the extracted text.

    Args:
        lines: List of strings containing the Markdown changelog content
        pr_marker: PR reference to search for (e.g., '#31')

    Returns:
        List of strings containing the matched bullet points with their sub-bullets,
        with PR markers removed

    Example:
        >>> lines = [
        ...     "- Feature: Add new API #31",
        ...     "  - Add endpoint for users",
        ...     "  - Add authentication #31",
        ...     "- Bug fix: Fix typo #32"
        ... ]
        >>> extract_pr_changes(lines, "#31")
        ['- Feature: Add new API',
         '  - Add endpoint for users',
         '  - Add authentication']

    Implementation Notes:
        1. Bullet detection uses regex patterns:
           - Top-level: Exactly '- ' at start of line
           - Sub-bullet: 2+ spaces followed by '- '
        2. Continuation lines (indented non-bullet lines) are kept with their parent bullet
        3. Blank lines within a bullet structure are preserved
        4. Non-indented lines that aren't bullets are treated as section breaks
        5. PR markers are only removed from lines where they appear, not from entire blocks
    """

    results: List[str] = []
    capture: bool = (
        False  # Tracks if we're currently capturing a bullet point block
    )
    current_bullet: List[
        str
    ] = []  # Accumulates lines for current bullet point

    # Compile regex patterns for bullet point detection
    bullet_start_pattern = re.compile(r"^\-\s")  # Matches top-level bullets
    sub_bullet_pattern = re.compile(r"^\s{2,}\-\s")  # Matches sub-bullets

    for line in lines:
        # Remove trailing whitespace/newlines for consistent processing
        stripped_line = line.rstrip("\n")

        # Handle top-level bullets
        if bullet_start_pattern.match(stripped_line):
            # Save any previously captured bullet point block
            if capture and current_bullet:
                results.extend(current_bullet)
                current_bullet = []

            # Check if this bullet references our PR
            if pr_marker in stripped_line:
                capture = True
                # Remove PR marker while preserving rest of text
                bullet_line_without_marker = stripped_line.replace(
                    f" {pr_marker}", ""
                )
                current_bullet = [bullet_line_without_marker]
            else:
                capture = False
                current_bullet = []

        # Handle sub-bullets while capturing
        elif capture and sub_bullet_pattern.match(stripped_line):
            # Remove PR marker if present in sub-bullet
            if pr_marker in stripped_line:
                stripped_line = stripped_line.replace(f" {pr_marker}", "")
            current_bullet.append(stripped_line)

        # Handle continuation lines and other content
        else:
            if capture:
                # Keep indented lines or blank lines as part of current bullet
                if stripped_line.startswith(" ") or stripped_line == "":
                    # Remove PR marker if somehow present
                    if pr_marker in stripped_line:
                        stripped_line = stripped_line.replace(
                            f" {pr_marker}", ""
                        )
                    current_bullet.append(stripped_line)
                else:
                    # Non-indented, non-bullet line indicates end of bullet block
                    results.extend(current_bullet)
                    current_bullet = []
                    capture = False

    # Handle case where file ends while still capturing
    if capture and current_bullet:
        results.extend(current_bullet)

    return results


def parse_args() -> argparse.Namespace:
    """Parse and validate command line arguments.

    Returns:
        Namespace containing the parsed arguments:
        - changelog_path (Path): Path to changelog Markdown file
        - pr_number (str): PR number to search for (without '#')
    """
    parser = argparse.ArgumentParser(
        description="Extract changelog items referencing a specific PR marker, e.g. #31."
    )
    parser.add_argument(
        "changelog_path",
        type=Path,
        help="Path to the changelog markdown file.",
    )
    parser.add_argument(
        "pr_number",
        help="Pull request number to search for, e.g., '31' for #31.",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point for the changelog extraction tool.

    Parses command line arguments, reads the changelog file, extracts matching
    entries, and prints the results to stdout.

    Returns early with error message if changelog file doesn't exist.
    """
    args = parse_args()
    pr_marker = f"#{args.pr_number}"

    # Validate input file exists
    if not args.changelog_path.is_file():
        print(f"Error: {args.changelog_path} does not exist or is not a file.")
        return

    # Read and process the changelog
    with args.changelog_path.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    extracted = extract_pr_changes(lines, pr_marker)

    # Output results
    if extracted:
        # Print extracted lines with original formatting
        print("\n".join(extracted))
    else:
        print(f"No items found that reference {pr_marker}")


if __name__ == "__main__":
    main()
