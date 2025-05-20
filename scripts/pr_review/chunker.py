#!/usr/bin/env python3
import argparse
import logging
import os
import sys
from github import Github, GithubException

def setup_logging(debug=False):
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('chunker_debug.log'),
            logging.StreamHandler()
        ]
    )
    logging.info("=== STARTING PR CHUNKER ===")

def parse_args():
    parser = argparse.ArgumentParser(description='Split PR into review chunks')
    parser.add_argument('--repo', required=True, help='GitHub repository in owner/repo format')
    parser.add_argument('--pr', required=True, type=int, help='Pull request number')
    parser.add_argument('--base', required=True, help='Base commit SHA')
    parser.add_argument('--head', required=True, help='Head commit SHA')
    parser.add_argument('--output', required=True, help='Output markdown file path')
    parser.add_argument('--github-token', required=True, help='GitHub access token')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    return parser.parse_args()

def get_pr_diff(github_client, repo_name, pr_number):
    logging.debug(f"Fetching PR #{pr_number} from repo {repo_name}")
    try:
        repo = github_client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        commits = list(pr.get_commits())
        logging.info(f"PR Title: {pr.title}")
        logging.info(f"PR Author: {pr.user.login}")
        logging.info(f"Commit count: {len(commits)}")
        logging.debug(f"First commit: {commits[0].sha if commits else 'None'}")
        logging.debug(f"Last commit: {commits[-1].sha if commits else 'None'}")
        return pr
    except GithubException as e:
        logging.error(f"Failed to fetch PR: {str(e)}")
        raise

def process_changes(pr, base_sha, head_sha):
    logging.info("Processing changes...")
    files = pr.get_files()
    file_changes = []
    for file in files:
        logging.debug(f"File: {file.filename}")
        logging.debug(f"Status: {file.status}")
        logging.debug(f"Changes: {file.changes} additions, {file.deletions} deletions")
        logging.debug(f"Patch preview: {file.patch[:100] if file.patch else 'No patch'}")
        file_changes.append({
            'filename': file.filename,
            'status': file.status,
            'additions': file.additions,
            'deletions': file.deletions,
            'patch': file.patch
        })
    return file_changes

def create_chunks(file_changes):
    logging.info("Creating review chunks...")
    chunks = []
    for change in file_changes:
        chunk = {
            'files': [change['filename']],
            'description': f"Review {change['filename']} ({change['status']})",
            'changes': f"{change['additions']} additions, {change['deletions']} deletions",
            'type': get_file_type(change['filename'])
        }
        chunks.append(chunk)
        logging.debug(f"Created chunk: {chunk['description']}")
    logging.info(f"Created {len(chunks)} chunks")
    return chunks

def get_file_type(filename):
    if filename.endswith('.py'):
        return 'python'
    elif filename.endswith('.js') or filename.endswith('.ts'):
        return 'javascript'
    elif filename.endswith('.go'):
        return 'golang'
    elif filename.endswith('.md'):
        return 'documentation'
    return 'other'

def generate_markdown(chunks, output_file):
    logging.info(f"Generating markdown output to {output_file}")
    with open(output_file, 'w') as f:
        f.write("# PR Review Chunks\n\n")
        f.write("Here are the logical chunks for review:\n\n")
        for i, chunk in enumerate(chunks, 1):
            f.write(f"## Chunk {i}: {chunk['description']}\n")
            f.write(f"- **Files**: {', '.join(chunk['files'])}\n")
            f.write(f"- **Changes**: {chunk['changes']}\n")
            f.write(f"- **Type**: {chunk['type']}\n\n")
        f.write("\n## Review Instructions\n")
        f.write("1. Assign each chunk to a reviewer\n")
        f.write("2. Reviewers should comment with '/reviewed chunk-X' when done\n")
    logging.debug("Markdown generation complete")

def main():
    args = parse_args()
    setup_logging(args.debug)
    try:
        logging.debug("Initializing GitHub client")
        github_client = Github(args.github_token)
        pr = get_pr_diff(github_client, args.repo, args.pr)
        file_changes = process_changes(pr, args.base, args.head)
        logging.info(f"Found {len(file_changes)} changed files")
        chunks = create_chunks(file_changes)
        generate_markdown(chunks, args.output)
        logging.info("=== PROCESS COMPLETED SUCCESSFULLY ===")
        return 0
    except Exception as e:
        logging.error("=== PROCESS FAILED ===")
        logging.error(f"Error: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
