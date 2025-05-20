#!/usr/bin/env python3
import argparse
import sys
from collections import defaultdict
import libcst as cst
from github import Github

class ChunkVisitor(cst.CSTVisitor):
    def __init__(self):
        self.chunks = []
        self.current_class = None

    def visit_ClassDef(self, node):
        self.current_class = node.name.value
        self.chunks.append({
            "type": "Class",
            "name": node.name.value,
            "start": node.start.line,
            "end": node.end.line,
        })
        # Continue visiting to find methods
        super().visit_ClassDef(node)
        self.current_class = None

    def visit_FunctionDef(self, node):
        chunk_name = node.name.value
        if self.current_class:
            chunk_name = f"{self.current_class}.{node.name.value}"
            
        self.chunks.append({
            "type": "Function",
            "name": chunk_name,
            "start": node.start.line,
            "end": node.end.line,
        })

def get_chunks_from_code(code):
    try:
        tree = cst.parse_module(code)
        visitor = ChunkVisitor()
        tree.visit(visitor)
        return visitor.chunks
    except Exception as e:
        print(f"DEBUG: Exception during parsing: {e}", file=sys.stderr)
        return []

def chunk_assigner(chunks, reviewers):
    assignments = defaultdict(list)
    for idx, chunk in enumerate(chunks):
        reviewer = reviewers[idx % len(reviewers)]
        assignments[reviewer].append(chunk)
    return assignments

def extract_reviewers(pr):
    reviewers = set()
    try:
        for r in pr.get_review_requests()[0]:
            reviewers.add(f"@{r.login}")
        for review in pr.get_reviews():
            if review.user:
                reviewers.add(f"@{review.user.login}")
    except Exception as e:
        print(f"DEBUG: Exception extracting reviewers: {e}", file=sys.stderr)
    return list(reviewers) or ["@vishnukoyyada", "@kvishnuv1403"]

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

    reviewers = extract_reviewers(pr)
    print(f"DEBUG: Reviewers detected: {reviewers}", file=sys.stderr)

    all_chunks = []
    file_map = {}

    for f in pr.get_files():
        print(f"DEBUG: Processing file: {f.filename}", file=sys.stderr)
        if not f.filename.endswith(".py"):
            print(f"DEBUG: Skipping non-Python file: {f.filename}", file=sys.stderr)
            continue

        try:
            file_content = repo.get_contents(f.filename, ref=args.head).decoded_content.decode()
            print(f"DEBUG: Successfully fetched content for {f.filename}", file=sys.stderr)
        except Exception as e:
            print(f"DEBUG: Could not fetch file content for {f.filename} at {args.head}: {e}", file=sys.stderr)
            continue

        chunks = get_chunks_from_code(file_content)
        print(f"DEBUG: Found {len(chunks)} chunks in {f.filename}: {chunks}", file=sys.stderr)
        
        if chunks:
            for chunk in chunks:
                chunk["file"] = f.filename
                chunk["link"] = f"https://github.com/{args.repo}/blob/{args.head}/{f.filename}#L{chunk['start']}-L{chunk['end']}"
            all_chunks.extend(chunks)
            file_map[f.filename] = chunks

    if not all_chunks:
        print(f"# PR Review Chunks (PR #{args.pr})\nRepository: {args.repo}\n\nNo functions or classes detected for chunking in changed Python files.")
        sys.exit(0)

    assignments = chunk_assigner(all_chunks, reviewers)

    # Generate the output
    output = [
        f"# PR Review Chunks (PR #{args.pr})",
        f"Repository: {args.repo}",
        f"Reviewers: {', '.join(reviewers)}\n"
    ]
    
    for reviewer, chunks in assignments.items():
        output.append(f"\n## Reviewer: {reviewer}")
        grouped_by_file = defaultdict(list)
        for chunk in chunks:
            grouped_by_file[chunk['file']].append(chunk)
        
        for filename, file_chunks in grouped_by_file.items():
            output.append(f"\n### File: `{filename}`")
            for chunk in file_chunks:
                symbol = "🧠" if chunk['type'] == "Function" else "🏛️"
                output.append(f"- {symbol} **{chunk['type']}**: `{chunk['name']}`")
                output.append(f"  - Lines: {chunk['start']}–{chunk['end']}")
                output.append(f"  - [View Code]({chunk['link']})")

    print("\n".join(output))

if __name__ == "__main__":
    main()