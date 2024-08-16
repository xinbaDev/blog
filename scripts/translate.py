import os
import glob
import subprocess
import re
import yaml

from openai import OpenAI

client = OpenAI()

def translate_text(text, target_language):
    lines = text.split("\n")
    translated_lines = []
    for line in lines:
        if line.strip():
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a translator. Please translate the following text to {target_language}. 
                         Do not translate image like ![](https://i.imgur.com/xxx.jpg) but keep it as it is",
                    },
                    {"role": "user", "content": line},
                ],
                model="gpt-4",
            )
            print(response)
            translated_lines.append(response.choices[0].message.content.strip())
        else:
            translated_lines.append("")  # Preserve empty lines
    return "\n".join(translated_lines)

def translate_blog_post(content, target_language):
    # Separate the front matter and the content
    front_matter_match = re.match(r"---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not front_matter_match:
        return content  # Return the original content if parsing fails

    front_matter = front_matter_match.group(1)
    body_content = front_matter_match.group(2)

    # Load the front matter as YAML
    front_matter_yaml = yaml.safe_load(front_matter)

    # Translate specific fields in the front matter
    if 'Title' in front_matter_yaml:
        front_matter_yaml['Title'] = translate_text(front_matter_yaml['Title'], target_language)
    if 'Summary' in front_matter_yaml:
        front_matter_yaml['Summary'] = translate_text(front_matter_yaml['Summary'], target_language)

    # Translate the body content
    translated_content = translate_text(body_content, target_language)

    # Reconstruct the translated post
    translated_front_matter = yaml.dump(front_matter_yaml, default_flow_style=False, allow_unicode=True).strip()
    return f"---\n{translated_front_matter}\n---\n{translated_content}"

def get_changed_files():
    # Get the list of files changed in the last commit
    result = subprocess.run(['git', 'diff', '--name-only', 'HEAD^', 'HEAD'], stdout=subprocess.PIPE)
    changed_files = result.stdout.decode('utf-8').splitlines()
    return [file for file in changed_files if file.startswith('content/en/') and file.endswith('.md')]

def translate_files():
    languages = {
        'ja': 'Japanese',
    }
    changed_files = get_changed_files()

    for file_path in changed_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        for lang_code, lang_name in languages.items():
            translated_content = translate_blog_post(content, lang_name)

            # Construct the new file path
            new_file_path = file_path.replace("content/en/", f"content/{lang_code}/")

            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(new_file_path), exist_ok=True)

            # Write the translated content to the new file
            translated_file_path = new_file_path.replace(".md", f".md")

            with open(translated_file_path, 'w', encoding='utf-8') as translated_file:
                translated_file.write(translated_content)

if __name__ == "__main__":
    translate_files()
