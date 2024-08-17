import os
import glob
import subprocess
import re
import yaml

from openai import OpenAI

client = OpenAI()

def proofread_text(text):
    lines = text.split("\n")
    revised_lines = []
    for line in lines:
        if line.strip():
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a proofreader. Please improve the following writing.",
                    },
                    {"role": "user", "content": line},
                ],
                model="gpt-4",
            )
            print(response)
            revised_lines.append(response.choices[0].message.content.strip())
        else:
            revised_lines.append("")  # Preserve empty lines
    return "\n".join(revised_lines)

def proofread_blog_post(content):
    # Separate the front matter and the content
    front_matter_match = re.match(r"---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not front_matter_match:
        return content  # Return the original content if parsing fails

    front_matter = front_matter_match.group(1)
    body_content = front_matter_match.group(2)

    # Load the front matter as YAML
    front_matter_yaml = yaml.safe_load(front_matter)

    # proofread specific fields in the front matter
    if 'Title' in front_matter_yaml:
        front_matter_yaml['Title'] = proofread_text(front_matter_yaml['Title'])
    if 'Summary' in front_matter_yaml:
        front_matter_yaml['Summary'] = proofread_text(front_matter_yaml['Summary'])

    # proofread the body content
    revised_content = proofread_text(body_content)

    # Reconstruct the revised post
    revised_front_matter = yaml.dump(front_matter_yaml, default_flow_style=False, allow_unicode=True).strip()
    return f"---\n{revised_front_matter}\n---\n{revised_content}"

def get_changed_files():
    # Get the list of files changed in the last commit
    result = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'], stdout=subprocess.PIPE)
    changed_files = result.stdout.decode('utf-8').splitlines()
    return [file for file in changed_files if file.startswith('content/en/') and file.endswith('.md')]

def proofread_files():
    
    changed_files = get_changed_files()
    print(changed_files)

    for file_path in changed_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

            revised_content = proofread_blog_post(content)

            # Write the revised content to the new file
            # revised_file_path = file_path.replace(".md", f".revised.md")

            with open(file_path, 'w', encoding='utf-8') as revised_file:
                revised_file.write(revised_content)


proofread_files()
