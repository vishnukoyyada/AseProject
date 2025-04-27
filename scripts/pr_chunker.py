import os
import libcst as cst
from git import Repo
from github import Github

def main():
    # Get environment variables
    repo_path = os.getenv('GITHUB_WORKSPACE')
    github_token = os.getenv('GITHUB_TOKEN')
    pr_number = int(os.getenv('PR_NUMBER'))
    
    # Initialize GitHub API
    g = Github(github_token)
    repo = g.get_repo(os.getenv('GITHUB_REPOSITORY'))
    pr = repo.get_pull(pr_number)
    
    # Get branch info
    base_branch = pr.base.ref
    feature_branch = pr.head.ref
    
    # Analyze changes
    chunks = analyze_pr_changes(repo_path, base_branch, feature_branch)
    
    # Generate markdown output
    with open('pr_chunks.md', 'w') as f:
        f.write(f"# PR #{pr_number} Review Chunks\n\n")
        f.write(f"Original PR: {pr.html_url}\n\n")
        
        for file_path, file_chunks in chunks.items():
            f.write(f"## File: {file_path}\n\n")
            for chunk in file_chunks:
                f.write(f"### {chunk['name']}\n")
                f.write(f"**Type**: {chunk['type']}\n\n")
                f.write("```diff\n")
                f.write(chunk['diff'])
                f.write("\n```\n\n")
                f.write("---\n\n")

def analyze_pr_changes(repo_path, base_branch, feature_branch):
    repo = Repo(repo_path)
    diffs = repo.git.diff(base_branch, feature_branch, name_only=True).split('\n')
    
    chunks = {}
    
    for file_path in diffs:
        if not file_path.endswith('.py'):  # Can add other file types
            continue
            
        try:
            # Get diff content
            diff_content = repo.git.diff(base_branch, feature_branch, file_path)
            
            # Parse both versions
            old_content = repo.git.show(f"{base_branch}:{file_path}")
            new_content = repo.git.show(f"{feature_branch}:{file_path}")
            
            old_tree = cst.parse_module(old_content)
            new_tree = cst.parse_module(new_content)
            
            # Identify changed components
            chunks[file_path] = identify_changed_components(old_tree, new_tree, diff_content)
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    return chunks

def identify_changed_components(old_tree, new_tree, diff_content):
    # This is a simplified version - you'd want to implement proper AST comparison
    chunks = []
    
    # Example: Find all functions in new tree
    for node in new_tree.body:
        if isinstance(node, cst.FunctionDef):
            chunks.append({
                'name': node.name.value,
                'type': 'function',
                'diff': extract_function_diff(diff_content, node.name.value)
            })
        elif isinstance(node, cst.ClassDef):
            chunks.append({
                'name': node.name.value,
                'type': 'class',
                'diff': extract_class_diff(diff_content, node.name.value)
            })
    
    return chunks

def extract_function_diff(full_diff, function_name):
    # Simplified diff extraction - implement proper parsing for your needs
    lines = full_diff.split('\n')
    function_diff = []
    in_function = False
    
    for line in lines:
        if f"def {function_name}(" in line:
            in_function = True
        if in_function:
            function_diff.append(line)
            if line.strip() == '':
                break
    
    return '\n'.join(function_diff)

if __name__ == "__main__":
    main()