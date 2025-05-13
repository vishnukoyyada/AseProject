#!/usr/bin/env python3
import os
import argparse
import libcst as cst
from git import Repo
from github import Github
from typing import Dict, List, Optional, Tuple, Any
import traceback
import sys
import math
from collections import defaultdict

# Configuration
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
        metadata = self.get_metadata(cst.metadata.PositionProvider, node)
        start = metadata.start.line
        end = metadata.end.line
        
        self.chunks.append((
            type_,
            node.name.value,
            (start, end)
        )

def get_reviewers_count(github_token: str, repo_name: str, pr_number: int) -> int:
    """Get number of requested reviewers for the PR"""
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    return len(pr.requested_reviewers)

def distribute_chunks(chunks: List[Tuple], num_reviewers: int) -> Dict[int, List[Tuple]]:
    """Distribute chunks evenly among reviewers"""
    chunks_per_reviewer = math.ceil(len(chunks) / num_reviewers)
    distribution = defaultdict(list)
    
    for i, chunk in enumerate(chunks):
        reviewer_idx = i // chunks_per_reviewer
        distribution[reviewer_idx].append(chunk)
    
    return distribution

def analyze_changes(repo: Repo, base: str, head: str) -> Dict[str, List]:
    """Enhanced change analysis with diff context"""
    changed_files = repo.git.diff(f"{base}..{head}", name_only=True).splitlines()
    chunks = {}
    
    for file_path in changed_files:
        if not file_path.endswith('.py'):
            continue
            
        new_content = repo.git.show(f"{head}:{file_path}")
        if not new_content:
            continue

        wrapper = cst.metadata.MetadataWrapper(cst.parse_module(new_content))
        collector = ChunkCollector()
        wrapper.visit(collector)
        
        chunks[file_path] = collector.chunks
    
    return chunks

def generate_output(chunks: Dict[str, List], pr_number: int, repo_name: str, 
                   output_file: str, head: str, reviewers_count: int) -> Dict[str, Any]:
    """Generate markdown output with review assignments"""
    output = {
        'single_file': len(chunks) == 1,
        'reviewers_count': reviewers_count,
        'assignments': defaultdict(list),
        'file_chunks': chunks
    }
    
    # Case 1: Single file, single reviewer
    if len(chunks) == 1 and reviewers_count == 1:
        file_path, file_chunks = next(iter(chunks.items()))
        output['assignments'][0] = [(file_path, *chunk) for chunk in file_chunks]
    
    # Case 2: Multiple files, single reviewer
    elif reviewers_count == 1:
        for file_path, file_chunks in chunks.items():
            output['assignments'][0].extend([(file_path, *chunk) for chunk in file_chunks])
    
    # Case 3: Single file, multiple reviewers
    elif len(chunks) == 1:
        file_path, file_chunks = next(iter(chunks.items()))
        distribution = distribute_chunks(file_chunks, reviewers_count)
        for reviewer_idx, chunks in distribution.items():
            output['assignments'][reviewer_idx].extend([(file_path, *chunk) for chunk in chunks])
    
    # Case 4: Multiple files, multiple reviewers
    else:
        all_chunks = []
        for file_path, file_chunks in chunks.items():
            all_chunks.extend([(file_path, *chunk) for chunk in file_chunks])
        
        distribution = distribute_chunks(all_chunks, reviewers_count)
        for reviewer_idx, chunks in distribution.items():
            output['assignments'][reviewer_idx] = chunks
    
    # Generate markdown output
    with open(output_file, 'w') as f:
        f.write(f"# PR #{pr_number} Review Assignments\n\n")
        f.write(f"**Repository**: {repo_name}\n")
        f.write(f"**Files Changed**: {len(chunks)}\n")
        f.write(f"**Reviewers**: {reviewers_count}\n\n")
        
        for reviewer_idx, assignment in output['assignments'].items():
            f.write(f"## Reviewer {reviewer_idx + 1}\n\n")
            
            # Group by file for better organization
            file_groups = defaultdict(list)
            for file_path, typ, name, lines in assignment:
                file_groups[file_path].append((typ, name, lines))
            
            for file_path, chunks in file_groups.items():
                f.write(f"### 📄 {file_path}\n\n")
                for typ, name, (start, end) in chunks:
                    f.write(f"- {'🔹' if typ == 'function' else '🔸'} {name} (lines {start}-{end})\n")
                    f.write(f"  [View Code](https://github.com/{repo_name}/blob/{head}/{file_path}#L{start}-L{end})\n\n")
                f.write("\n")
            f.write("---\n\n")
    
    return output

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", default="chunks.md")
    parser.add_argument("--github-token", required=True)
    args = parser.parse_args()

    try:
        repo = Repo(os.getcwd())
        chunks = analyze_changes(repo, args.base, args.head)
        
        if not chunks:
            print("No reviewable chunks found.")
            return
            
        reviewers_count = get_reviewers_count(args.github_token, args.repo, args.pr)
        if reviewers_count == 0:
            reviewers_count = 1  # Default to 1 reviewer if none assigned
            
        output = generate_output(
            chunks=chunks,
            pr_number=args.pr,
            repo_name=args.repo,
            output_file=args.output,
            head=args.head,
            reviewers_count=reviewers_count
        )
        
        print(f"Generated review assignments for {len(chunks)} files with {reviewers_count} reviewers")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()