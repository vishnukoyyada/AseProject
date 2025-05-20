#!/usr/bin/env python3
import argparse
import logging
import sys
import libcst as cst
from github import Github
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChunkVisitor(cst.CSTVisitor):
    def __init__(self):
        self.chunks = []
        self.current_class = None

    def visit_ClassDef(self, node):
        self.current_class = node.name.value
        self.chunks.append({
            "type": "Class",
            "name": node.name.value,
            "class": None,
            "start": node.start.line,
            "end": node.end.line
        })
        # Continue visiting to find methods
        super().visit_ClassDef(node)
        self.current_class = None

    def visit_FunctionDef(self, node):
        chunk_name = node.name.value
        if self.current_class:
            chunk_name = f"{self.current_class}.{chunk_name}"
            
        self.chunks.append({
            "type": "Function",
            "name": chunk_name,
            "class": self.current_class,
            "start": node.start.line,
            "end": node.end.line
        })

def get_chunks_from_code(code, filename):
    try:
        tree = cst.parse_module(code)
        visitor = ChunkVisitor()
        tree.visit(visitor)
        return visitor.chunks
    except Exception as e:
        logger.warning(f"Failed to parse {filename}: {str(e)}")
        return []

def distribute_chunks(chunks, reviewers):
    if not chunks or not reviewers:
        return {}
    
    # Simple round-robin distribution
    distribution = defaultdict(list)
    for i, chunk in enumerate(chunks):
        reviewer = reviewers[i % len(reviewers)]
        distribution[reviewer].append(chunk)
    
    return distribution

def generate_markdown_output(repo_name, pr_number, chunk_distribution, base_url):
    output = []
    output.append(f"# PR Review Chunks (PR #{pr_number})")
    output.append(f"Repository: {repo_name}\n")
    
    if not chunk_distribution:
        output.append("No functions or classes detected for chunking in changed Python files.")
        return "\n".join(output)
    
    for reviewer, chunks in chunk_distribution.items():
        output.append(f"## Reviewer: {reviewer}")
        
        # Group chunks by file
        file_groups = defaultdict(list)
        for chunk in chunks:
            file_groups[chunk['file']].append(chunk)
        
        for file, file_chunks in file_groups.items():
            output.append(f"### File: {file}")
            for chunk in file_chunks:
                emoji = "🛠️" if chunk['type'] == 'Function' else "🏛️"
                output.append(f"- {emoji} {chunk['type']}: `{chunk['name']}`")
                output.append(f"  - Lines: {chunk['start']}-{chunk['end']}")
                link = f"{base_url}/{file}#L{chunk['start']}-L{chunk['end']}"
                output.append(f"  - [View Code]({link})")
            output.append("")  # Add empty line between files
        
        output.append("")  # Add empty line between reviewers
    
    return "\n".join(output)

def get_reviewers(pr, default_reviewers):
    # Try to get requested reviewers first
    requested_reviewers = [f"@{r.login}" for r in pr.get_review_requests()[0]]
    if requested_reviewers:
        return requested_reviewers
    
    # Fall back to default reviewers if none are requested
    return default_reviewers

def main():
    parser = argparse.ArgumentParser(description='PR Chunker')
    parser.add_argument('--repo', required=True, help='GitHub repository in owner/repo format')
    parser.add_argument('--pr', required=True, type=int, help='Pull request number')
    parser.add_argument('--base', required=True, help='Base commit SHA')
    parser.add_argument('--head', required=True, help='Head commit SHA')
    parser.add_argument('--github-token', required=True, help='GitHub access token')
    args = parser.parse_args()

    g = Github(args.github_token)
    repo = g.get_repo(args.repo)
    pr = repo.get_pull(args.pr)

    # Get reviewers (requested first, fallback to defaults)
    default_reviewers = ["@vishnukoyyada", "@kvishnuv1403"]
    reviewers = get_reviewers(pr, default_reviewers)
    
    all_chunks = []
    base_url = f"https://github.com/{args.repo}/blob/{args.head}"
    
    for f in pr.get_files():
        if not f.filename.endswith(".py"):
            continue
            
        try:
            file_content = repo.get_contents(f.filename, ref=args.head).decoded_content.decode()
            chunks = get_chunks_from_code(file_content, f.filename)
            
            # Add file information to each chunk
            for chunk in chunks:
                chunk['file'] = f.filename
            all_chunks.extend(chunks)
            
        except Exception as e:
            logger.error(f"Failed to process {f.filename}: {str(e)}")
            continue
    
    # Distribute chunks among reviewers
    chunk_distribution = distribute_chunks(all_chunks, reviewers)
    
    # Generate markdown output
    markdown_output = generate_markdown_output(args.repo, args.pr, chunk_distribution, base_url)
    print(markdown_output)

if __name__ == "__main__":
    main()