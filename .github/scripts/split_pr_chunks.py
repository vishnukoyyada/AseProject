import ast
import os

def get_chunks_from_file(file_path):
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())
        chunks = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                chunks.append(f"Function: {node.name}")
            elif isinstance(node, ast.ClassDef):
                chunks.append(f"Class: {node.name}")
        return chunks
    except:
        return []

changed_files = os.popen("git diff --name-only origin/main").read().splitlines()

with open("chunk_output.txt", "w") as output:
    for file in changed_files:
        if file.endswith(".py"):
            output.write(f"📄 {file}:\n")
            chunks = get_chunks_from_file(file)
            for chunk in chunks:
                output.write(f"  - {chunk}\n")
            output.write("\n")
