import markdown
import re
from publications import read_bib_file, read_bib_dblp, gen_html_by_database
from datetime import date
import sys

def generate_content(content_filename, bib_database):
    with open(content_filename, 'r') as f:
        lines = f.readlines()

    sections = [('', [])]

    for line in lines:
        if line[0] == '#':
            section_name = line[1:].strip()
            sections.append((section_name, []))
        elif line[0] == '-':
            if len(sections[-1][1]) == 0 or sections[-1][1][-1][0] != 'list':
                sections[-1][1].append(('list', []))
            sections[-1][1][-1][1].append(line[1:].strip())
        elif line[0] == '*':
            item, description = line[1:].strip().split(':', 1)
            sections[-1][1].append(('list-item', item, description))
        elif len(line.strip()) > 0:
            sections[-1][1].append(('paragraph', line.strip()))

    def format_string_as_html(s):
        return re.sub(r'<a ([^>]*)>', r'<a \1 target="_blank">', markdown.markdown(s)).encode('ascii', 'xmlcharrefreplace').decode()

    def print_html(section_part, indent=16):
        if section_part[0] == 'paragraph':
            return '{}{}\n'.format(' ' * indent, format_string_as_html(section_part[1]))
        elif section_part[0] == 'list':
            return '{}{}\n'.format(' ' * indent, format_string_as_html('- ' + '\n- '.join(section_part[1])).replace('<li>', ' ' * (indent + 4) + '<li>').replace('</ul>', ' ' * indent + '</ul>'))
        elif section_part[0] == 'list-item':
            return '{}{}\n'.format(' ' * indent, """<div class="list-row">
                    <div class="list-item">{}:</div>
                    <div class="list-description">{}</div>
                </div>""".format(re.sub(r'-+', '&mdash;', section_part[1]), format_string_as_html(section_part[2])[3:-4]))

    name = sections[0][1][0][1]
    links = [s[1] for s in sections[0][1][1:]]

    def links_bar(links):
        s = ''
        for link in links:
            if 'dblp.org' in link:
                s += '<a href="{}" class="social-link" target="_blank"><img src="images/dblp.svg" height="18"></a>\n'.format(link)
            elif 'scholar.google.com' in link:
                s += '<a href="{}" class="social-link" target="_blank"><img src="images/google-scholar.svg" height="20"></a>\n'.format(link)
            elif 'instagram.com' in link:
                s += '<a href="{}" class="social-link" target="_blank"><i class="fa fa-instagram"></i></a>\n'.format(link)
            elif 'twitter.com' in link:
                s += '<a href="{}" class="social-link" target="_blank"><i class="fa fa-twitter"></i></a>\n'.format(link)
            elif 't.me' in link:
                s += '<a href="{}" class="social-link" target="_blank"><i class="fa fa-telegram"></i></a>'.format(link)
            else:
                print('WARNING: unsupported social link: {}'.format(link))
        return s
    
    def section_title(section_str):
        if '#' in section_str:
            return section_str.split('#')[0].strip()
        else:
            return section_str.strip()
        
    def section_menu_item(section_str):
        if '#' in section_str:
            return section_str.split('#')[-1].strip()
        else:
            return section_str.strip()

    def id(section_str):
        return re.sub(r'\s+', '-', section_menu_item(section_str).lower())

    menu = ('\n' + ' ' * 12).join(['<li class="navi-item"><a href="#{}" onclick="close_sidebar()">{}</a></li>'.format(id(section[0]), section_menu_item(section[0])) for section in sections[1:]])
    
    # content = ('\n' + ' ' * 12).join([section)
    content = ''

    for section in sections[1:]:
        content += ' ' * 12 + '<div id = "{}">\n'.format(id(section[0]))
        content += ' ' * 16 + '<h1>{}</h1>\n'.format(section_title(section[0]))
        if section[0] == 'Publications': 
            content += gen_html_by_database(bib_database)
        else: 
            for section_part in section[1]:
                content += print_html(section_part)
        content += ' ' * 12 + '</div>\n\n'

    return name, menu, links_bar(links), content



# Main body of the script
input_content_file = 'content.md'
input_bib_file = None
input_bib_link = None
template_file = 'template.html'
output_file = 'index.html'

args = sys.argv

if '-h' in args or '--help' in args:
    print("Usage: python html-generator.py [-il link-to-dblp | -if input-bib-file=bibliography.bib] [-t template-file=template.html] [-o output-file=index.html]")
    print("If both -il and -if arguments are present, -if is used")
    print("The order of arguments is not important")
    print("The DBLP link should be to the author's page, not his bibliography page, e.g., 'https://dblp.org/pid/160/0973.html'")
    exit(0)

for i in range(1, len(args)):
    if args[i] == '-il':
        input_bib_link = args[i + 1]
    elif args[i] == '-if':
        input_bib_file = args[i + 1]
    elif args[i] == '-ic':
        input_content_file = args[i + 1]
    elif args[i] == '-t':
        template_file = args[i + 1]
    elif args[i] == '-o':
        output_file = args[i + 1]

if input_bib_link is None and input_bib_file is None:
    input_bib_file = 'bibliography.bib'

if input_bib_file is not None:
    bib_database = read_bib_file(input_bib_file)
else:
    print('Downloading bibliography...')
    bib_database=read_bib_dblp(input_bib_link)

name, menu, links, content = generate_content(input_content_file, bib_database)

with open(template_file, 'r') as f:
    template = f.read()
with open(output_file, 'w') as f:
    f.write(template.format(name, menu, links, date.today().strftime("%d %B %Y"), content))