#!/usr/bin/env python3
import os
import argparse
import libcst as cst
from git import Repo
from github import Github
from typing import Dict, List, Optional, Tuple
import traceback
import sys

DEBUG = True  # Set to False in production

class ChunkCollector(cst.CSTVisitor):
    """Enhanced collector with line number tracking"""
    def __init__(self):
        self.chunks = []
    
    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self._add_chunk('function', node)
        return False
        
    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self._add_chunk('class', node)
        return False
    
    def _add_chunk(self, type_: str, node):
        self.chunks.append((
            type_,
            node.name.value,
            (node.start.line, node.end.line)
        ))
        if DEBUG:
            print(f"Found {type_}: {node.name.value} (lines {node.start.line}-{node.end.line})")

def debug_print(*args, **kwargs):
    """Conditional debug output"""
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)

def get_file_content(repo: Repo, commit_sha: str, file_path: str) -> Optional[str]:
    """Get file content at specific commit"""
    try:
        return repo.git.show(f"{commit_sha}:{file_path}")
    except Exception as e:
        debug_print(f"File not found at {commit_sha}: {file_path}")
        return None

def process_chunks(chunks: List[Tuple[str, str, Tuple[int, int]]], diff_text: str) -> List[Tuple[str, str, Tuple[int, int]]]:
    """Filter chunks based on whether they intersect with lines in the diff"""
    changed_lines = set()
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            # Parse the hunk header
            parts = line.split(" ")
            if len(parts) > 2:
                added_info = parts[2]
                if ',' in added_info:
                    start, count = map(int, added_info[1:].split(","))
                    changed_lines.update(range(start, start + count))
                else:
                    changed_lines.add(int(added_info[1:]))
    
    filtered_chunks = [
        chunk for chunk in chunks
        if any(l in changed_lines for l in range(chunk[2][0], chunk[2][1] + 1))
    ]
    
    return filtered_chunks

def analyze_changes(repo: Repo, base: str, head: str) -> Dict[str, List]:
    """Enhanced change analysis with diff context"""
    try:
        changed_files = repo.git.diff(f"{base}..{head}", name_only=True).splitlines()
        debug_print(f"Changed files: {changed_files}")
        
        chunks = {}
        for file_path in changed_files:
            if not file_path.endswith('.py'):
                debug_print(f"Skipping non-Python file: {file_path}")
                continue
                
            try:
                debug_print(f"\nProcessing {file_path}")
                
                old_content = get_file_content(repo, base, file_path)
                new_content = get_file_content(repo, head, file_path)
                debug_print(f"File sizes - old: {len(old_content or '')} bytes, new: {len(new_content)} bytes")

                new_tree = cst.parse_module(new_content)
                collector = ChunkCollector()
                new_tree.visit(collector)
                
                file_diff = repo.git.diff(f"{base}..{head}", "--unified=0", file_path)
                chunks[file_path] = process_chunks(collector.chunks, file_diff)
                
            except Exception as e:
                print(f"⚠️ Error processing {file_path}: {str(e)}")
                if DEBUG:
                    traceback.print_exc()
                continue
                
        return chunks
        
    except Exception as e:
        print(f"❌ Critical error in analyze_changes: {str(e)}")
        traceback.print_exc()
        raise

def generate_output(
    chunks: Dict[str, List[Tuple[str, str, Tuple[int, int]]]],
    pr_number: int,
    repo_name: str,
    output_file: str,
    min_lines: int,
    max_lines: int
):
    """Generate markdown file of chunks"""
    try:
        with open(output_file, "w") as f:
            f.write(f"# Code Chunks in PR #{pr_number} - {repo_name}\n\n")
            for file, items in chunks.items():
                if not items:
                    continue
                f.write(f"## `{file}`\n\n")
                for item_type, name, (start, end) in items:
                    lines = end - start + 1
                    if lines < min_lines or lines > max_lines:
                        continue
                    f.write(f"- `{item_type}` **{name}** (lines {start}-{end}, {lines} lines)\n")
                f.write("\n")
        debug_print(f"✅ Output written to {output_file}")
    except Exception as e:
        print(f"❌ Error writing output: {str(e)}")
        traceback.print_exc()
        raise

def main():
    """Main entry point with enhanced error handling"""
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--repo", required=True)
        parser.add_argument("--pr", type=int, required=True)
        parser.add_argument("--base", required=True)
        parser.add_argument("--head", required=True)
        parser.add_argument("--min-lines", type=int, default=200)
        parser.add_argument("--max-lines", type=int, default=800)
        parser.add_argument("--output", default="chunks.md")
        args = parser.parse_args()

        debug_print("\n" + "="*40)
        debug_print("PR Chunker Debug Information")
        debug_print("="*40)
        debug_print(f"Repository: {args.repo}")
        debug_print(f"PR Number: {args.pr}")
        debug_print(f"Base SHA: {args.base}")
        debug_print(f"Head SHA: {args.head}")
        debug_print(f"Output file: {args.output}\n")

        repo = Repo(os.getcwd())
        debug_print(f"Repo initialized at: {repo.working_dir}")

        try:
            if repo.head.is_detached:
                debug_print(f"Detached HEAD at commit: {repo.head.commit.hexsha[:7]}")
            else:
                debug_print(f"Active branch: {repo.active_branch.name}")
        except Exception as e:
            debug_print(f"Could not determine branch state: {str(e)}")

        chunks = analyze_changes(repo, args.base, args.head)
        generate_output(
            chunks=chunks,
            pr_number=args.pr,
            repo_name=args.repo,
            output_file=args.output,
            min_lines=args.min_lines,
            max_lines=args.max_lines
        )
        
        debug_print("\nChunker completed successfully")
        
    except Exception as e:
        print(f"\n❌ Fatal error in PR Chunker: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
