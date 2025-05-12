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
    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)
    
    def __init__(self):
        self.chunks = []
    
    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self._add_chunk('function', node)
        return False
        
    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self._add_chunk('class', node)
        return False
    
    def _add_chunk(self, type_: str, node):
        # Get line numbers from metadata
        metadata = self.get_metadata(cst.metadata.PositionProvider, node)
        start = metadata.start.line
        end = metadata.end.line
        
        self.chunks.append((
            type_,
            node.name.value,
            (start, end)
        ))
        if DEBUG:
            print(f"Found {type_}: {node.name.value} (lines {start}-{end})")

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
                
                new_content = get_file_content(repo, head, file_path)
                debug_print(f"File size: {len(new_content)} bytes")

                # Parse with position metadata
                wrapper = cst.metadata.MetadataWrapper(
                    cst.parse_module(new_content)
                )
                collector = ChunkCollector()
                wrapper.visit(collector)
                
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

# [Rest of your existing functions remain the same...]

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