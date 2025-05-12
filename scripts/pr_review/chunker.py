#!/usr/bin/env python3
import os
import argparse
import libcst as cst
from git import Repo
from github import Github
from typing import Dict, List, Optional, Tuple
import traceback
import sys

# Configuration
DEBUG = True  # Set to False in production

# Debug utilities
def debug_print(*args, **kwargs):
    """Conditional debug output"""
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)

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
        metadata = self.get_metadata(cst.metadata.PositionProvider, node)
        start = metadata.start.line
        end = metadata.end.line
        
        self.chunks.append((
            type_,
            node.name.value,
            (start, end)
        ))
        if DEBUG:
            debug_print(f"Found {type_}: {node.name.value} (lines {start}-{end})")

def get_file_content(repo: Repo, commit_sha: str, file_path: str) -> Optional[str]:
    """Get file content at specific commit"""
    try:
        return repo.git.show(f"{commit_sha}:{file_path}")
    except Exception as e:
        debug_print(f"File not found at {commit_sha}: {file_path} - {str(e)}")
        return None

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
                if not new_content:
                    continue
                    
                debug_print(f"File size: {len(new_content)} bytes")

                wrapper = cst.metadata.MetadataWrapper(
                    cst.parse_module(new_content)
                )
                collector = ChunkCollector()
                wrapper.visit(collector)
                
                file_diff = repo.git.diff(f"{base}..{head}", "--unified=0", file_path)
                chunks[file_path] = [
                    (typ, name, lines) 
                    for typ, name, lines in collector.chunks
                ]
                
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

def generate_output(chunks: Dict, pr_number: int, repo_name: str, output_file: str, head: str):
    """Generate markdown output"""
    try:
        with open(output_file, 'w') as f:
            f.write(f"# PR #{pr_number} Review Chunks\n\n")
            f.write(f"**Repository**: {repo_name}\n\n")
            
            if not chunks:
                f.write("No reviewable chunks found.\n")
                return
                
            for file_path, file_chunks in chunks.items():
                f.write(f"## 📄 {file_path}\n\n")
                for typ, name, (start, end) in file_chunks:
                    f.write(f"### {'🔹' if typ == 'function' else '🔸'} {name}\n")
                    f.write(f"Lines {start}-{end}\n\n")
                    f.write(f"[View Code](https://github.com/{repo_name}/blob/{head}/{file_path}#L{start}-L{end})\n\n")
                f.write("---\n\n")
                
        debug_print(f"Output written to {output_file}")
        
    except Exception as e:
        print(f"❌ Error generating output: {str(e)}")
        traceback.print_exc()
        raise

def main():
    """Main entry point"""
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--repo", required=True)
        parser.add_argument("--pr", type=int, required=True)
        parser.add_argument("--base", required=True)
        parser.add_argument("--head", required=True)
        parser.add_argument("--output", default="chunks.md")
        args = parser.parse_args()

        debug_print("\n" + "="*40)
        debug_print("PR Chunker Debug Information")
        debug_print("="*40)
        debug_print(f"Repository: {args.repo}")
        debug_print(f"PR Number: {args.pr}")
        debug_print(f"Base SHA: {args.base[:7]}")
        debug_print(f"Head SHA: {args.head[:7]}")
        debug_print(f"Output file: {args.output}\n")

        repo = Repo(os.getcwd())
        debug_print(f"Repo initialized at: {repo.working_dir}")

        chunks = analyze_changes(repo, args.base, args.head)
        generate_output(
            chunks=chunks,
            pr_number=args.pr,
            repo_name=args.repo,
            output_file=args.output,
            head=args.head  # Pass head here
        )
        
        debug_print("Chunker completed successfully")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
