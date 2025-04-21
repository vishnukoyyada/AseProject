import os
from github import Github

# Load GitHub context
repo_name = os.environ["GITHUB_REPOSITORY"]
pr_number = os.environ["GITHUB_REF"].split("/")[-1]

g = Github(os.environ["GITHUB_TOKEN"])
repo = g.get_repo(repo_name)
pr = repo.get_pull(int(pr_number))

# Read chunk output
with open("chunk_output.txt", "r") as f:
    comment_body = f"### 🔍 Chunk Analysis Result\n\n```\n{f.read()}\n```"

# Post comment
pr.create_issue_comment(comment_body)
