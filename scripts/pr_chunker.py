import os
import libcst as cst
from git import Repo
from github import Github
from typing import Dict, List, Optional

def main():
    try:
        # Get environment variables
        repo_path = os.getenv('GITHUB_WORKSPACE', '.')
        github_token = os.getenv('GITHUB_TOKEN')
        pr_number = int(os.getenv('PR_NUMBER', '0'))
        base_ref = os.getenv('BASE_REF', 'main')
        head_ref = os.getenv('HEAD_REF', 'HEAD')
        github_repo = os.getenv('GITHUB_REPOSITORY')

        print(f"Starting PR chunker for PR #{pr_number}")
        print(f"Comparing {base_ref}..{head_ref} in {github_repo}")

        # Initialize Git repo
        repo = Repo(repo_path)
        
        # Verify we have the branches
        print("\nAvailable branches:")
        for branch in repo.branches:
            print(f" - {branch.name}")

        # Analyze changes
        chunks = analyze_pr_changes(repo, base_ref, head_ref)
        
        # Generate markdown output
        generate_markdown_output(chunks, pr_number, github_repo, github_token)

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        raise

def analyze_pr_changes(repo: Repo, base_ref: str, head_ref: str) -> Dict[str, List]:
    print(f"\nAnalyzing changes between {base_ref} and {head_ref}")
    
    # Get changed files
    diff_cmd = f"{base_ref}...{head_ref}"
    diffs = repo.git.diff(diff_cmd, name_only=True).split('\n')
    diffs = [d.strip() for d in diffs if d.strip()]
    
    print(f"\nFound {len(diffs)} changed files:")
    for f in diffs:
        print(f" - {f}")

    chunks = {}
    
    for file_path in diffs:
        if not file_path.endswith('.py'):
            continue
            
        try:
            print(f"\nProcessing {file_path}")
            
            # Get diff content for this file
            file_diff = repo.git.diff(diff_cmd, file_path)
            
            # Get file content at both refs
            try:
                old_content = repo.git.show(f"{base_ref}:{file_path}")
            except:
                old_content = ""  # File is newly added
                
            new_content = repo.git.show(f"{head_ref}:{file_path}")

            # Parse ASTs
            old_tree = cst.parse_module(old_content) if old_content else None
            new_tree = cst.parse_module(new_content)
            
            # Identify changed components
            file_chunks = identify_changed_components(old_tree, new_tree, file_diff)
            
            if file_chunks:
                chunks[file_path] = file_chunks
                print(f"Found {len(file_chunks)} chunks in {file_path}")
                
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            continue
                
    return chunks

def identify_changed_components(
    old_tree: Optional[cst.Module], 
    new_tree: cst.Module, 
    file_diff: str
) -> List[Dict]:
    chunks = []
    
    # Visitor to collect function/class definitions
    class DefinitionCollector(cst.CSTVisitor):
        def __init__(self):
            self.definitions = []
        
        def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
            self.definitions.append(('function', node.name.value))
            return False
            
        def visit_ClassDef(self, node: cst.ClassDef) -> bool:
            self.definitions.append(('class', node.name.value))
            return False
    
    # Get all definitions from new tree
    collector = DefinitionCollector()
    new_tree.visit(collector)
    
    # For each definition, extract its diff
    for def_type, def_name in collector.definitions:
        try:
            chunk_diff = extract_definition_diff(file_diff, def_type, def_name)
            if chunk_diff:
                chunks.append({
                    'name': def_name,
                    'type': def_type,
                    'diff': chunk_diff
                })
        except Exception as e:
            print(f"Error extracting {def_type} {def_name}: {str(e)}")
    
    return chunks

def extract_definition_diff(
    full_diff: str, 
    def_type: str, 
    def_name: str
) -> Optional[str]:
    lines = full_diff.split('\n')
    chunk_lines = []
    in_chunk = False
    indent = ' ' * 4
    
    for line in lines:
        if def_type == 'function' and line.startswith('+def ') and def_name in line:
            in_chunk = True
        elif def_type == 'class' and line.startswith('+class ') and def_name in line:
            in_chunk = True
            
        if in_chunk:
            chunk_lines.append(line)
            # Check for end of definition
            if line.strip() == '' or \
               (not line.startswith('+') and not line.startswith('-') and not line.startswith(' ')):
                break
    
    return '\n'.join(chunk_lines) if chunk_lines else None

def generate_markdown_output(
    chunks: Dict[str, List], 
    pr_number: int, 
    github_repo: str, 
    github_token: str
):
    print("\nGenerating markdown output...")
    
    with open('pr_chunks.md', 'w') as f:
        # Header
        f.write(f"# PR #{pr_number} Review Chunks\n\n")
        f.write(f"Repository: {github_repo}\n\n")
        
        if not chunks:
            f.write("No Python files with reviewable chunks found.\n")
            return
        
        # Summary
        f.write("## Summary\n")
        total_chunks = sum(len(v) for v in chunks.values())
        f.write(f"Found {total_chunks} reviewable chunks across {len(chunks)} files.\n\n")
        
        # File sections
        for file_path, file_chunks in chunks.items():
            f.write(f"## File: `{file_path}`\n\n")
            
            for chunk in file_chunks:
                f.write(f"### {chunk['type'].title()} `{chunk['name']}`\n")
                f.write("```diff\n")
                f.write(chunk['diff'])
                f.write("\n```\n\n")
                f.write("---\n\n")
    
    print("Markdown output generated successfully.")

if __name__ == "__main__":
    main()