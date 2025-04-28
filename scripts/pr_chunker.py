import os
import libcst as cst
from git import Repo
from github import Github
from typing import Dict, List, Optional

class DefinitionCollector(cst.CSTVisitor):
    """Collects function and class definitions from a CST tree."""
    def __init__(self):
        self.definitions = []
    
    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self.definitions.append(('function', node.name.value))
        return False
        
    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self.definitions.append(('class', node.name.value))
        return False

def main():
    """Main entry point for the PR chunker script."""
    try:
        # Initialize and validate environment
        repo_path = os.getenv('GITHUB_WORKSPACE', '.')
        github_token = os.getenv('GITHUB_TOKEN')
        pr_number = int(os.getenv('PR_NUMBER', '0'))
        base_sha = os.getenv('BASE_SHA')
        head_sha = os.getenv('HEAD_SHA')
        github_repo = os.getenv('GITHUB_REPOSITORY')

        if not all([github_token, base_sha, head_sha]):
            raise ValueError("Missing required environment variables")

        print(f"Starting PR chunker for PR #{pr_number}")
        print(f"Comparing {base_sha[:7]} (base)..{head_sha[:7]} (head) in {github_repo}")

        # Initialize Git repo and GitHub client
        repo = Repo(repo_path)
        github_client = Github(github_token)
        
        # Fetch the specific commits we need to compare
        repo.git.fetch('origin', base_sha)
        repo.git.fetch('origin', head_sha)

        # Analyze changes and generate output
        chunks = analyze_pr_changes(repo, base_sha, head_sha)
        generate_markdown_output(chunks, pr_number, github_repo, github_client)

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        raise

def analyze_pr_changes(repo: Repo, base_sha: str, head_sha: str) -> Dict[str, List]:
    """Analyze changes between two commits and identify logical chunks."""
    print(f"\nAnalyzing changes between {base_sha[:7]} and {head_sha[:7]}")
    
    # Get list of changed files
    diff_cmd = f"{base_sha}..{head_sha}"
    diffs = repo.git.diff(diff_cmd, name_only=True).split('\n')
    diffs = [d.strip() for d in diffs if d.strip()]
    
    print(f"\nFound {len(diffs)} changed files:")
    for file_path in diffs:
        print(f" - {file_path}")

    chunks = {}
    
    for file_path in diffs:
        if not file_path.endswith('.py'):
            continue
            
        try:
            print(f"\nProcessing {file_path}")
            
            # Get diff and content for this file
            file_diff = repo.git.diff(diff_cmd, file_path)
            old_content = get_file_content(repo, base_sha, file_path)
            new_content = get_file_content(repo, head_sha, file_path)

            # Parse and analyze the code
            old_tree = cst.parse_module(old_content) if old_content else None
            new_tree = cst.parse_module(new_content)
            file_chunks = identify_changed_components(old_tree, new_tree, file_diff)
            
            if file_chunks:
                chunks[file_path] = file_chunks
                print(f"Found {len(file_chunks)} chunks in {file_path}")
                
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            continue
                
    return chunks

def get_file_content(repo: Repo, sha: str, file_path: str) -> str:
    """Get file content at a specific commit."""
    try:
        return repo.git.show(f"{sha}:{file_path}")
    except:
        return ""  # File didn't exist at this commit

def identify_changed_components(
    old_tree: Optional[cst.Module], 
    new_tree: cst.Module, 
    file_diff: str
) -> List[Dict]:
    """Identify changed functions/classes in the diff."""
    collector = DefinitionCollector()
    new_tree.visit(collector)
    
    chunks = []
    for def_type, def_name in collector.definitions:
        chunk_diff = extract_definition_diff(file_diff, def_type, def_name)
        if chunk_diff:
            chunks.append({
                'name': def_name,
                'type': def_type,
                'diff': chunk_diff
            })
    
    return chunks

def extract_definition_diff(
    full_diff: str, 
    def_type: str, 
    def_name: str
) -> Optional[str]:
    """Extract the diff for a specific definition from the full file diff."""
    lines = full_diff.split('\n')
    chunk_lines = []
    in_chunk = False
    
    for line in lines:
        # Check for start of our definition
        if not in_chunk:
            if def_type == 'function' and line.startswith('+def ') and def_name in line:
                in_chunk = True
            elif def_type == 'class' and line.startswith('+class ') and def_name in line:
                in_chunk = True
            continue
            
        # Collect lines until we hit a break
        chunk_lines.append(line)
        if line.strip() == '' or line.startswith('diff --git'):
            break
    
    return '\n'.join(chunk_lines) if chunk_lines else None

def generate_markdown_output(
    chunks: Dict[str, List], 
    pr_number: int, 
    github_repo: str, 
    github_client: Github
):
    """Generate markdown output with review chunks."""
    print("\nGenerating markdown output...")
    
    with open('pr_chunks.md', 'w') as f:
        # Header
        f.write(f"# PR #{pr_number} Review Chunks\n\n")
        f.write(f"Repository: {github_repo}\n\n")
        
        if not chunks:
            f.write("No Python files with reviewable chunks found.\n")
            return
        
        # Summary
        total_chunks = sum(len(v) for v in chunks.values())
        f.write(f"## Summary\nFound {total_chunks} reviewable chunks across {len(chunks)} files.\n\n")
        
        # File sections
        for file_path, file_chunks in chunks.items():
            f.write(f"## File: `{file_path}`\n\n")
            
            for chunk in file_chunks:
                f.write(f"### {chunk['type'].title()} `{chunk['name']}`\n")
                f.write("```diff\n")
                f.write(chunk['diff'])
                f.write("\n```\n\n")
                f.write("---\n\n")

if __name__ == "__main__":
    main()