#!/usr/bin/env python3
import argparse
import logging
import sys
import libcst as cst
from github import Github

REVIEWERS = ["@vishnukoyyada", "@kvishnuv1403"]  # Add more as needed

class ChunkVisitor(cst.CSTVisitor):
    def __init__(self):
        self.chunks = []

    def visit_FunctionDef(self, node):
        self.chunks.append({
            "type": "Function",
            "name": node.name.value,
            "start": node.body.start.line,
            "end": node.body.end.line
        })

    def visit_ClassDef(self, node):
        self.chunks.append({
            "type": "Class",
            "name": node.name.value,
            "start": node.body.start.line,
            "end": node.body.end.line
        })

def get_chunks_from_code(code):
    try:
        tree = cst.parse_module(code)
        visitor = ChunkVisitor()
        tree.visit(visitor)
        return visitor.chunks
    except Exception:
        return []

def main():
    parser = argparse.ArgumentParser(description='PR Chunker')
    parser.add_argument('--repo', required=True)
    parser.add_argument('--pr', required=True, type=int)
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--github-token', required=True)
    args = parser.parse_args()

    g = Github(args.github_token)
    repo = g.get_repo(args.repo)
    pr = repo.get_pull(args.pr)

    print(f"# PR Review Chunks (PR #{args.pr})")
    print(f"Repository: {args.repo}")

    reviewer_idx = 0
    chunk_count = 0

    for f in pr.get_files():
        if not f.filename.endswith(".py"):
            continue
        # Get file content at head commit
        file_content = repo.get_contents(f.filename, ref=args.head).decoded_content.decode()
        chunks = get_chunks_from_code(file_content)
        if not chunks:
            continue
        for chunk in chunks:
            reviewer = REVIEWERS[reviewer_idx % len(REVIEWERS)]
            reviewer_idx += 1
            chunk_count += 1
            print(f"\n## Chunk {chunk_count}")
            print(f"Reviewer: {reviewer}")
            print(f"File: {f.filename}")
            print(f"– {chunk['type']}: {chunk['name']}")
            print(f"– Lines: {chunk['start']}–{chunk['end']}")
            print(f"L{chunk['end']} View Code")
            link = f"https://github.com/{args.repo}/blob/{args.head}/{f.filename}#L{chunk['start']}-L{chunk['end']}"
            print(f"– Link: {link}")

    if chunk_count == 0:
        print("\nNo functions or classes detected for chunking in changed Python files.")

if __name__ == "__main__":
    main()
