import bibtexparser
import Levenshtein
import re
import requests
import io
from pylatexenc.latex2text import LatexNodes2Text
tex_converter = LatexNodes2Text()

def read_bib_file(filename):
    with open(filename, 'r') as f:
        bib_database = bibtexparser.load(f)
    return bib_database
    
def read_bib_dblp(profile_link):
    bib_link = re.sub(r'html$', 'bib?param=1', profile_link)
    return bibtexparser.load(io.StringIO(requests.get(bib_link, allow_redirects=True).content.decode('UTF-8')))
    

def gen_html_by_database(bib_database, rename_conferences=False):
    # get rid of PhD thesis, it should not be in the list of publications
    # also I am lazy to process @misc items
    bib_database.entries = [entry for entry in bib_database.entries if entry['ENTRYTYPE'] not in ('phdthesis', 'misc')]

    # shortening IDs, DBLP format is too long and is not convenient to use
    for entry in bib_database.entries:
        # IDsuffix is needed to get rid of the duplicated IDs later
        entry['IDsuffix'] = entry['ID'].split('/')[-2]
        entry['ID'] = entry['ID'].split('/')[-1]

    # searching for duplicated IDs
    appearances = dict()
    for entry in bib_database.entries:
        if entry['ID'] in appearances:
            appearances[entry['ID']] += 1
        else:
            appearances[entry['ID']] = 1
    duplicated_ids = [i for i in appearances if appearances[i] > 1]

    # changing duplicated IDs
    for entry in bib_database.entries:
        if entry['ID'] in duplicated_ids:
            entry['ID'] = entry['ID'] + entry['IDsuffix']
        
    # removing unnecessary fields
    for entry in bib_database.entries:
        opt_fields = ['url', 'doi', 'eprinttype', 'eprint']
        for field in opt_fields:
            if field in entry:
                entry['OPT' + field] = entry.pop(field)
        if 'editor' in entry and entry['ENTRYTYPE'] != 'book':
            entry['OPTeditor'] = entry.pop('editor')
        unnecessary_fields = ['timestamp', 'biburl', 'bibsource', 'IDsuffix']
        for field in unnecessary_fields:
            del entry[field]

    # renaming conferences and journals, 
    # this part of the script must be customized according to your personal needs and preferences
    if rename_conferences:
        for entry in bib_database.entries:
            if entry['ENTRYTYPE'] == 'inproceedings':
                if 'booktitle' not in entry:
                    continue
                # GECCO
                if 'GECCO' in entry['booktitle']:
                    entry['booktitle'] = 'Genetic and Evolutionary Computation Conference, {{GECCO}} {}'.format(entry['year'])
                # PPSN
                if 'PPSN' in entry['booktitle']:
                    if 'Part' in entry['booktitle']: 
                        # I am counting on the part being in the end of the booktitle
                        entry['booktitle'] = 'Parallel Problem Solving from Nature, {{PPSN}} {}, Part {}'.format(entry['year'], entry['booktitle'].split()[-1])
                    else:
                        entry['booktitle'] = 'Parallel Problem Solving from Nature, {{PPSN}} {}'.format(entry['year'])
                # FOGA
                if 'FOGA' in entry['booktitle']:
                    entry['booktitle'] = 'Foundations of Genetic Algorithms, {{FOGA}} {}'.format(entry['year'])
                # CEC
                if 'CEC' in entry['booktitle']:
                    entry['booktitle'] = 'Congress on Evolutionary Computation, {{CEC}} {}'.format(entry['year'])
                # EvoCOP
                if 'EvoCOP' in entry['booktitle']:
                    entry['booktitle'] = 'Evolutionary Computation in Combinatorial Optimization, {{E}}vo{{COP}} {}'.format(entry['year'])
            if entry['ENTRYTYPE'] == 'article':
                if 'journal' not in entry:
                    continue
                if entry['journal'] == '{ACM} Trans. Evol. Learn. Optim.':
                    entry['journal'] = '{ACM} Transactions on Evolutionary Learning and Optimization'
                

    # writer in bibtexparser library messes up the order of items, 
    # and its alignment is far from beautiful, so I have to write my own writer
    def write_entry(entry):
        # the following value is needed for beautiful alignment
        longest_field_name = max(len(field_name) for field_name in entry.keys() if field_name != 'ENTRYTYPE')

        s = '@article{{{},\n'.format(entry['ID'])
        # the preferred order of fields can be defined here 
        fields_order = ['author', 'OPTeditor', 'editor', 'title', 'booktitle', 'journal', 'volume', 'number', 'series', 'pages', 'publisher', 'year']
        
        # we first write the fields from the order we defined
        for field in fields_order:
            if field in entry:
                # 
                s += '    {} = {{{}}},\n'.format(field.ljust(longest_field_name + 1, ' '), entry[field].replace('\n', '\n' + ' ' * (longest_field_name + 9)))
        
        # then we write the rest of non-OPT fields
        for field in entry:
            if field not in fields_order and field[:3] != 'OPT' and field != 'ENTRYTYPE' and field != 'ID':
                s += '    {} = {{{}}},\n'.format(field.ljust(longest_field_name + 1, ' '), entry[field].replace('\n', '\n' + ' ' * (longest_field_name + 9)))

        # OPT fields come the last
        for field in entry:
            if field[:3] == 'OPT' and field not in fields_order and field != 'ENTRYTYPE' and field != 'ID':
                s += '    {} = {{{}}},\n'.format(field.ljust(longest_field_name + 1, ' '), entry[field].replace('\n', '\n' + ' ' * (longest_field_name + 9)))
        s += '}\n'

        return s

    # adding the well-formatted bib item as a string 
    for entry in bib_database.entries:
        entry['bibstr'] = write_entry(entry)

    # matching arxiv papers to the conference or journal ones by title
    matched_ids = set()

    for entry in bib_database.entries:
        if 'journal' in entry and entry['journal'] == 'CoRR':
            # find entries with the same title
            # beware of too similar titles of different papers! 
            # the Levenshtein distance is used to get rid of stupid
            # small differences in the bibtex titles taken from dblp
            for other_entry in bib_database.entries:
                if ('journal' not in other_entry or other_entry['journal'] != 'CoRR') and Levenshtein.distance(entry['title'].casefold(), other_entry['title'].casefold()) < 10:
                    if 'arxiv-link' in other_entry:
                        print('WARNING: replacing arXiv link for item {}'.format(other_entry['ID']))
                    other_entry['arxiv-link'] = 'https://arxiv.org/{}'.format(entry['volume'])
                    print('Added link to arxiv paper {} to paper {}'.format(entry['OPTeprint'], other_entry['ID']))
                    if entry['ID'] not in matched_ids:
                        matched_ids.add(entry['ID'])

            # if not found, ask the user
            if entry['ID'] not in matched_ids:
                same_author_entries = [other_entry for other_entry in bib_database.entries if ('journal' not in other_entry or other_entry['journal'] != 'CoRR') and 'author' in other_entry and other_entry['author'] == entry['author']]
                
                print('Did not find a matching title for {} (year {}), titled "{}"'.format(entry['OPTeprint'], entry['year'], entry['title'].replace('\n', ' ')))
                print('Select possible option:')
                for i in range(len(same_author_entries)):
                    print('({}) {}: "{}"'.format(i, same_author_entries[i]['ID'], same_author_entries[i]['title'].replace('\n', ' ')))
                i = len(same_author_entries)
                print('({}) Enter ID manually'.format(i))
                print('({}) Count this paper as a journal paper'.format(i + 1))
                print('({}) Do not mention this paper'.format(i + 2))
                

                while True:
                    j = input()
                    try:
                        j = int(j)
                    except ValueError:
                        print('Non-integer input, try again')
                        continue
                    if 0 <= j < i:
                        same_author_entries[j]['arxiv-link'] = 'https://arxiv.org/{}'.format(entry['volume'])
                        matched_ids.add(entry['ID'])
                        break
                    elif j == i:
                        print('Enter ID:')
                        paper_id = input()
                        if paper_id not in [other_entry['ID'] for other_entry in bib_database.entries]:
                            print('ID not found, choose your option again')
                            continue
                        for other_entry in bib_database.entries:
                            if other_entry['ID'] == paper_id:
                                other_entry['arxiv-link'] = 'https://arxiv.org/{}'.format(entry['volume'])
                                break
                        break
                    elif j == i + 1:
                        break
                    elif j == i + 2:
                        matched_ids.add(entry['ID'])
                        entry['arxiv-link'] = 'https://arxiv.org/{}'.format(entry['volume'])
                        break
                    else:
                        print('Input is not a correct number, try again')
                        continue

    # Filtering the rest of entries we need
    entries = [entry for entry in bib_database.entries if 'journal' not in entry or entry['journal'] != 'CoRR' or entry['ID'] not in matched_ids]

    # Fixing the titles and authors for HTML-readable format
    def latex_to_html(title):
        return tex_converter.latex_to_text(title).encode('ascii', 'xmlcharrefreplace').decode()
        
    for entry in entries:
        entry['title'] = latex_to_html(entry['title'])
        if 'author' in entry:
            entry['author'] = latex_to_html(entry['author'])

    # now we are actually making a text for bibitem
    def authors(bib_authors):
        authors_list = [s.strip() for s in bib_authors.split(' and\n')]
        if len(authors_list) == 1:
            return bib_authors
        elif len(authors_list) == 2:
            return ' and '.join(authors_list)
        else:
            authors_list[-1] = 'and ' + authors_list[-1]
            return ', '.join(authors_list)

    def text(entry):
        if entry['ENTRYTYPE'] == 'inproceedings':
            if 'pages' not in entry:
                pages = ''
            elif entry['pages'] == 'to appear':
                pages = ', to appear'
            else: 
                pages = ', pp. {}'.format(entry['pages'].replace('--', '&mdash;'))
            return '<i>{}.</i> {}. In <i>{}</i>{}. {}.'.format(authors(entry['author']), entry['title'], re.sub(r'[\{\}]', '', entry['booktitle']), pages, re.sub(r'[\{\}]', '', entry['publisher']).replace('\\\"u', '&uuml') + ', ' + entry['year'] if 'publisher' in entry else entry['year'])
        elif entry['ENTRYTYPE'] == 'article':
            journal = re.sub(r'([^\\]|^)[{}]', r'\1', entry['journal'])
            if 'pages' in entry:
                return '<i>{}.</i> {}. <i>{}</i>, {}:{}, {}.'.format(authors(entry['author']), entry['title'], journal, entry['volume'], entry['pages'].replace('--', '&mdash;'), entry['year'])
            elif journal == 'CoRR':
                return '<i>{}.</i> {}. <i>{}</i>, {}, {}.'.format(authors(entry['author']), entry['title'], journal, entry['volume'], entry['year'])
            else:
                return '<i>{}.</i> {}. <i>{}</i>, {}.'.format(authors(entry['author']), entry['title'], journal, entry['year'])
        elif entry['ENTRYTYPE'] == 'incollection':
            if 'publisher' not in entry:
                publisher = ''
            else:
                publisher = entry['publisher'] + ' '
            return '<i>{}.</i> {}. In <i>{}</i>, {}, {} {}.'.format(authors(entry['author']), entry['title'], entry['booktitle'], entry['series'], publisher, entry['year'])
        elif entry['ENTRYTYPE'] == 'book':
            if 'publisher' not in entry:
                publisher = ''
            else:
                publisher = entry['publisher'] + ' '
            return '<i>{} (editors).</i> {}. {}, {}{}, ISBN {}'.format(authors(entry['editor']), entry['title'], entry['series'], publisher, entry['year'], entry['isbn'])
        else:
            print('ERROR: no support this type of entries: {}'.format([entry['ENTRYTYPE']]))


    def print_entry_html(entry):
        s = """                <div class="list-row">
                        <div class="list-item">
                            """
        if 'arxiv-link' in entry:
            s += '<a href="{}", target="_blank"><img src="images/arxiv-icon.svg" alt="arxiv icon", height="20px"></a>\n                        '.format(entry['arxiv-link'])
        s += """                        <div class="bibtex-button">
                                <img class="image-button" src="images/bibtex.png" alt="bibtex icon" height="20px" onclick="show('{}')" title="Open bibtex item">
                                <div class="bibtex-window bibtex-window-colors" id="{}">
    <pre>{}</pre>
                                </div>    
                            </div>
                            """.format(entry['ID'], entry['ID'], entry['bibstr'])
        if 'OPTurl' in entry:
            s += '<a href="{}", target="_blank"><img src="images/doi.png" alt="doi icon", height="20px"></a>\n                        '.format(entry['OPTurl'].replace('\_', '_'))
        s += """</div>
                        <div class="list-description">{}</div>
                    </div>
    """.format(text(entry))
        return s

    years = dict()
    for entry in entries:
        year = entry['year']
        if year not in years:
            years[year] = dict()
        entry_type = entry['ENTRYTYPE']
        if entry_type != 'inproceedings' and entry_type != 'article':
            entry_type = 'book'
        if entry_type == 'article' and entry['journal'] == 'CoRR':
            entry_type = 'arxiv'
        if entry_type not in years[year]:
            years[year][entry_type] = [entry]
        else:
            years[year][entry_type].append(entry)

    s = ""
    for year in reversed(sorted(list(years.keys()))):
        s += '{}<h2>{}</h2>\n'.format(' ' * 16, year)
        for entry_type, header_entry_type in ('article', 'Journal papers'), ('inproceedings', 'Conference papers'), ('arxiv', 'arXiv papers'), ('book', 'Books, bookchapters and other'):
            if entry_type in years[year]:
                s += '{}<h3>{}</h3>\n'.format(' ' * 16, header_entry_type)
                for entry in years[year][entry_type]:
                    s += print_entry_html(entry)
    return s


