import os
import argparse
import libcst as cst
from git import Repo
from github import Github
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv


load_dotenv()  # Loads .env file

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--min-lines", type=int, default=200)
    parser.add_argument("--max-lines", type=int, default=800)
    parser.add_argument("--output", default="chunks.md")
    args = parser.parse_args()

    try:
        repo = Repo(os.getcwd())
        gh = Github(os.getenv("PAT_TOKEN"))
        
        # Get smart chunks
        chunks = analyze_changes(repo, args.base, args.head)
        
        # Generate optimized output
        generate_output(
            chunks=chunks,
            pr_number=args.pr,
            repo_name=args.repo,
            output_file=args.output,
            min_lines=args.min_lines,
            max_lines=args.max_lines
        )
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

def analyze_changes(repo: Repo, base: str, head: str) -> Dict[str, List]:
    """Enhanced change analysis with diff context"""
    changed_files = repo.git.diff(f"{base}..{head}", name_only=True).splitlines()
    chunks = {}
    
    for file_path in changed_files:
        if not file_path.endswith('.py'):
            continue
            
        try:
            old_content = get_file_content(repo, base, file_path)
            new_content = get_file_content(repo, head, file_path)
            
            # Parse with line number tracking
            new_tree = cst.parse_module(new_content)
            collector = ChunkCollector()
            new_tree.visit(collector)
            
            # Get file diff for context
            file_diff = repo.git.diff(
                f"{base}..{head}",
                "--unified=0",
                file_path
            )
            
            chunks[file_path] = process_chunks(
                collector.chunks,
                file_diff
            )
            
        except Exception as e:
            print(f"Skipping {file_path}: {str(e)}")
            
    return chunks

def process_chunks(chunks: List[Tuple], diff: str) -> List[Dict]:
    """Enrich chunks with diff context"""
    result = []
    for type_, name, (start, end) in chunks:
        chunk_diff = extract_context(diff, type_, name, start, end)
        if chunk_diff:
            result.append({
                'type': type_,
                'name': name,
                'lines': (start, end),
                'diff': chunk_diff
            })
    return result

def extract_context(diff: str, type_: str, name: str, start: int, end: int) -> str:
    """Smart diff extraction with surrounding context"""
    # Implementation optimized for GitHub diff format
    lines = diff.splitlines()
    chunk_lines = []
    found = False
    
    for line in lines:
        if not found:
            if (type_ == 'function' and f"def {name}(" in line) or \
               (type_ == 'class' and f"class {name}(" in line):
                found = True
                chunk_lines.append(f"@@ -{start},0 +{end},0 @@")
        if found:
            chunk_lines.append(line)
            if len(chunk_lines) > 50:  # Reasonable context limit
                break
                
    return '\n'.join(chunk_lines) if found else None

def generate_output(chunks: Dict, pr_number: int, repo_name: str, 
                  output_file: str, min_lines: int, max_lines: int):
    """Optimized markdown generation"""
    with open(output_file, 'w') as f:
        f.write(f"# PR #{pr_number} Review Chunks\n\n")
        f.write(f"**Repository**: {repo_name}\n")
        f.write(f"**Chunk Size**: {min_lines}-{max_lines} lines\n\n")
        
        for file_path, file_chunks in chunks.items():
            f.write(f"## 📄 {file_path}\n\n")
            for chunk in file_chunks:
                f.write(f"### {'🔹' if chunk['type'] == 'function' else '🔸'} {chunk['name']}\n")
                f.write(f"*Lines {chunk['lines'][0]}-{chunk['lines'][1]}*\n\n")
                f.write("```diff\n")
                f.write(chunk['diff'])
                f.write("\n```\n\n")
                f.write("[Add Review Comment](#)\n\n---\n\n")

if __name__ == "__main__":
    main()
