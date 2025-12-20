"""
Script to help convert HTML files to Flask templates
Run this to extract common elements and create base template
"""
import re
from pathlib import Path

def extract_css_from_html(html_file):
    """Extract CSS from HTML file"""
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract style tag content
    css_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
    if css_match:
        return css_match.group(1)
    return ''

def extract_js_from_html(html_file):
    """Extract JavaScript from HTML file"""
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract script tags (non-module)
    js_matches = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
    return '\n\n'.join(js_matches)

def extract_module_js_from_html(html_file):
    """Extract module JavaScript from HTML file"""
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract module script tags
    module_js = re.findall(r'<script type="module">(.*?)</script>', content, re.DOTALL)
    return '\n\n'.join(module_js)

def create_base_template():
    """Create base template from index.html"""
    index_path = Path('index.html')
    
    if not index_path.exists():
        print("index.html not found!")
        return
    
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract head section
    head_match = re.search(r'<head>(.*?)</head>', content, re.DOTALL)
    head_content = head_match.group(1) if head_match else ''
    
    # Extract CSS
    css = extract_css_from_html(index_path)
    
    # Extract JS
    js = extract_js_from_html(index_path)
    module_js = extract_module_js_from_html(index_path)
    
    # Extract navbar
    nav_match = re.search(r'<!-- NAVBAR -->(.*?)<!-- HERO', content, re.DOTALL)
    navbar = nav_match.group(1) if nav_match else ''
    
    # Extract footer
    footer_match = re.search(r'<!-- FOOTER -->(.*?)</footer>', content, re.DOTALL)
    footer = footer_match.group(1) + '</footer>' if footer_match else ''
    
    # Create base template
    base_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Cryptasium | Tech. Curiosity. Visualized.{% endblock %}</title>
    <!-- Importing Inter Font -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <!-- Phosphor Icons -->
    <script src="https://unpkg.com/@phosphor-icons/web"></script>

    <style>
{css}
    </style>
</head>
<body>
    <!-- TUBES CURSOR CANVAS -->
    <canvas id="canvas"></canvas>

    <!-- PRELOADER -->
    <div id="preloader">
        <div class="loader-logo">C</div>
    </div>

    <!-- NAVBAR -->
    {navbar.replace('index.html', "{{ url_for('index') }}").replace('youtube.html', "{{ url_for('youtube_list') }}").replace('podcast.html', "{{ url_for('podcast_list') }}").replace('blog.html', "{{ url_for('blog_list') }}").replace('shorts.html', "{{ url_for('shorts_list') }}").replace('community.html', "{{ url_for('community_list') }}")}

    <!-- MAIN CONTENT -->
    {% block content %}{% endblock %}

    <!-- FOOTER -->
    {footer}

    <!-- JAVASCRIPT LOGIC -->
    <script>
{js}
    </script>

    <!-- TUBES CURSOR EFFECT -->
    <script type="module">
{module_js}
    </script>
</body>
</html>"""
    
    # Write base template
    base_path = Path('templates/base.html')
    base_path.parent.mkdir(exist_ok=True)
    with open(base_path, 'w', encoding='utf-8') as f:
        f.write(base_template)
    
    print(f"✅ Created {base_path}")
    print("⚠️  Please review and manually adjust the template as needed!")

if __name__ == '__main__':
    create_base_template()

