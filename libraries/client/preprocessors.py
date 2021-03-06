from __future__ import unicode_literals, print_function
import os
import re
from glob import glob
from shutil import copy
from libraries.app.app import App
from libraries.door43_tools.bible_books import BOOK_NUMBERS
from libraries.general_tools.file_utils import write_file, read_file
from libraries.resource_container.ResourceContainer import RC
from libraries.resource_container.ResourceContainer import BIBLE_RESOURCE_TYPES


def do_preprocess(rc, repo_dir, output_dir):
    if rc.resource.identifier == 'obs':
        App.logger.debug("do_preprocess: using ObsPreprocessor")
        preprocessor = ObsPreprocessor(rc, repo_dir, output_dir)
    elif rc.resource.identifier in BIBLE_RESOURCE_TYPES:
        App.logger.debug("do_preprocess: using BiblePreprocessor")
        preprocessor = BiblePreprocessor(rc, repo_dir, output_dir)
    elif rc.resource.identifier == 'ta':
        App.logger.debug("do_preprocess: using TaPreprocessor")
        preprocessor = TaPreprocessor(rc, repo_dir, output_dir)
    elif rc.resource.identifier == 'tw':
        App.logger.debug("do_preprocess: using TwPreprocessor")
        preprocessor = TwPreprocessor(rc, repo_dir, output_dir)
    elif rc.resource.identifier == 'tq':
        App.logger.debug("do_preprocess: using TqPreprocessor")
        preprocessor = TqPreprocessor(rc, repo_dir, output_dir)
    else:
        App.logger.debug("do_preprocess: using Preprocessor")
        preprocessor = Preprocessor(rc, repo_dir, output_dir)
    return preprocessor.run(), preprocessor


class Preprocessor(object):
    ignoreDirectories = ['.git', '00']
    ignoreFiles = ['.DS_Store', 'reference.txt', 'title.txt', 'LICENSE.md', 'README.md']

    def __init__(self, rc, source_dir, output_dir):
        """
        :param RC rc: 
        :param string source_dir: 
        :param string output_dir: 
        """
        self.rc = rc
        self.source_dir = source_dir  # Local directory
        self.output_dir = output_dir  # Local directory

        # Write out the new manifest file based on the resource container
        write_file(os.path.join(self.output_dir, 'manifest.yaml'), self.rc.as_dict())

    def run(self):
        for idx, project in enumerate(self.rc.projects):
            project_path = os.path.join(self.source_dir, project.path)

            if os.path.isfile(project_path):
                # Case #1: Project path is a file, then we copy the file over to the output dir
                if project.identifier.lower() in BOOK_NUMBERS:
                    filename = '{0}-{1}.{2}'.format(BOOK_NUMBERS[project.identifier.lower()],
                                                    project.identifier.upper(), self.rc.resource.file_ext)
                else:
                    filename = '{0}-{1}.{2}'.format(str(idx + 1).zfill(2), project.identifier,
                                                    self.rc.resource.file_ext)
                copy(project_path, os.path.join(self.output_dir, filename))
            else:
                # Case #2: It's a directory of files, so we copy them over to the output directory
                files = glob(os.path.join(project_path, '*.{0}'.format(self.rc.resource.file_ext)))
                if len(files):
                    for file_path in files:
                        output_file_path = os.path.join(self.output_dir, os.path.basename(file_path))
                        if os.path.isfile(file_path) and not os.path.exists(output_file_path) \
                                and os.path.basename(file_path) not in self.ignoreFiles:
                            copy(file_path, output_file_path)
                else:
                    # Case #3: The project path is multiple chapters, so we piece them together
                    chapters = self.rc.chapters(project.identifier)
                    App.logger.debug("Merging chapters in '{0}'".format(project.identifier))
                    if len(chapters):
                        text = ''
                        for chapter in chapters:
                            text = self.mark_chapter(project.identifier, chapter, text)
                            for chunk in self.rc.chunks(project.identifier, chapter):
                                text = self.mark_chunk(project.identifier, chapter, chunk, text)
                                text += read_file(os.path.join(project_path, chapter, chunk))+"\n\n"
                        if project.identifier.lower() in BOOK_NUMBERS:
                            filename = '{0}-{1}.{2}'.format(BOOK_NUMBERS[project.identifier.lower()],
                                                            project.identifier.upper(), self.rc.resource.file_ext)
                        else:
                            filename = '{0}-{1}.{2}'.format(str(idx+1).zfill(2), project.identifier,
                                                            self.rc.resource.file_ext)
                        write_file(os.path.join(self.output_dir, filename), text)
        return True

    def mark_chapter(self, ident, chapter, text):
        return text  # default does nothing to text

    def mark_chunk(self, ident, chapter, chunk, text):
        return text  # default does nothing to text

    def is_multiple_jobs(self):
        return False

    def get_book_list(self):
        return None


class ObsPreprocessor(Preprocessor):
    def __init__(self, *args, **kwargs):
        super(ObsPreprocessor, self).__init__(*args, **kwargs)

    @staticmethod
    def get_chapters(project_path):
        chapters = []
        for chapter in sorted(os.listdir(project_path)):
            if os.path.isdir(os.path.join(project_path, chapter)) and chapter not in ObsPreprocessor.ignoreDirectories:
                chapters.append({
                    'id': chapter,
                    'title': ObsPreprocessor.get_chapter_title(project_path, chapter),
                    'reference': ObsPreprocessor.get_chapter_reference(project_path, chapter),
                    'frames': ObsPreprocessor.get_chapter_frames(project_path, chapter)
                })
        return chapters

    @staticmethod
    def get_chapter_title(project_path, chapter):
        """
        Get a chapter title.
        if the title file does not exist, it will hand back the number with a period only.
        """
        title_file = os.path.join(project_path, chapter, 'title.txt')
        if os.path.exists(title_file):
            contents = read_file(title_file)
            title = contents.strip()
        else:
            title = chapter.lstrip('0') + '. '
        return title

    @staticmethod
    def get_chapter_reference(project_path, chapter):
        """Get the chapters reference text"""
        reference_file = os.path.join(project_path, chapter, 'reference.txt')
        reference = ''
        if os.path.exists(reference_file):
            contents = read_file(reference_file)
            reference = contents.strip()
        return reference

    @staticmethod
    def get_chapter_frames(project_path, chapter):
        frames = []
        chapter_dir = os.path.join(project_path, chapter)
        for frame in sorted(os.listdir(chapter_dir)):
            if frame not in ObsPreprocessor.ignoreFiles:
                text = read_file(os.path.join(project_path, chapter, frame))
                frames.append({
                    'id': chapter + '-' + frame.strip('.txt'),
                    'text': text
                })
        return frames

    def is_chunked(self, project):
        chapters = self.rc.chapters(project.identifier)
        if chapters and len(chapters):
            chunks = self.rc.chunks(project.identifier, chapters[0])
            for chunk in chunks:
                if os.path.basename(chunk) in ['title.txt', 'reference.txt', '01.txt']:
                    return True
        return False

    def run(self):
        for project in self.rc.projects:
            project_path = os.path.join(self.source_dir, project.path)
            # Copy all the markdown files in the project root directory to the output directory
            for file_path in glob(os.path.join(project_path, '*.md')):
                output_file_path = os.path.join(self.output_dir, os.path.basename(file_path))
                if os.path.isfile(file_path) and not os.path.exists(output_file_path) \
                        and os.path.basename(file_path) not in self.ignoreFiles:
                    copy(file_path, output_file_path)
            if self.is_chunked(project):
                for chapter in self.get_chapters(project_path):
                    markdown = '# {0}\n\n'.format(chapter['title'])
                    for frame in chapter['frames']:
                        markdown += '![Frame {0}](https://cdn.door43.org/obs/jpg/360px/obs-en-{0}.jpg)\n\n' \
                            .format(frame.get('id'))
                        markdown += frame['text'] + '\n\n'
                    markdown += '_{0}_\n'.format(chapter['reference'])
                    output_file = os.path.join(self.output_dir, '{0}.md'.format(chapter.get('id')))
                    write_file(output_file, markdown)
            else:
                for chapter in self.rc.chapters(project.identifier):
                    f = None
                    if os.path.isfile(os.path.join(project_path, chapter, "01.md")):
                        f = os.path.join(project_path, chapter, '01.md')
                    elif os.path.isfile(os.path.join(project_path, chapter, 'intro.md')):
                        f = os.path.join(project_path, chapter, 'intro.md')
                    if f:
                        copy(f, os.path.join(self.output_dir, '{0}.md'.format(chapter)))
        return True


class BiblePreprocessor(Preprocessor):
    def __init__(self, *args, **kwargs):
        super(BiblePreprocessor, self).__init__(*args, **kwargs)
        self.books = []

    def is_multiple_jobs(self):
        return len(self.books) > 1

    def get_book_list(self):
        self.books.sort()
        return self.books

    def run(self):
        for idx, project in enumerate(self.rc.projects):
            project_path = os.path.join(self.source_dir, project.path)
            file_format = '{0}-{1}.usfm'

            # Case #1: The project path is a file, and thus is one book of the Bible, copy to standard filename
            if os.path.isfile(project_path):
                if project.identifier.lower() in BOOK_NUMBERS:
                    filename = file_format.format(BOOK_NUMBERS[project.identifier.lower()], project.identifier.upper())
                else:
                    filename = file_format.format(str(idx+1).zfill(2), project.identifier.upper())
                copy(project_path, os.path.join(self.output_dir, filename))
                self.books.append(filename)
            else:
                # Case #2: Project path is a dir with one or more USFM files, is one or more books of the Bible
                usfm_files = glob(os.path.join(project_path, '*.usfm'))
                if len(usfm_files):
                    for usfm_path in usfm_files:
                        book_code = os.path.splitext(os.path.basename(usfm_path))[0].split('-')[-1].lower()
                        if book_code in BOOK_NUMBERS:
                            filename = file_format.format(BOOK_NUMBERS[book_code], book_code.upper())
                        else:
                            filename = '{0}.usfm'.format(os.path.splitext(os.path.basename(usfm_path))[0])
                        output_file_path = os.path.join(self.output_dir, filename)
                        if os.path.isfile(usfm_path) and not os.path.exists(output_file_path):
                            copy(usfm_path, output_file_path)
                        self.books.append(filename)
                else:
                    # Case #3: Project path is a dir with one or more chapter dirs with chunk & title files
                    chapters = self.rc.chapters(project.identifier)
                    if len(chapters):
                        #          Piece the USFM file together
                        title_file = os.path.join(project_path, chapters[0], 'title.txt')
                        if os.path.isfile(title_file):
                            title = read_file(title_file)
                            title = re.sub(r' \d+$', '', title).strip()
                        else:
                            title = project.title
                        if not title and os.path.isfile(os.path.join(project_path, 'title.txt')):
                            title = read_file(os.path.join(project_path, 'title.txt'))
                        usfm = """
\\id {0} {1}
\\ide UTF-8
\\h {2}
\\toc1 {2}
\\toc2 {2}
\\mt {2}
""".format(project.identifier.upper(), self.rc.resource.title, title)
                        for chapter in chapters:
                            if chapter in self.ignoreDirectories:
                                continue
                            chapter_num = chapter.lstrip('0')
                            chunks = self.rc.chunks(project.identifier, chapter)
                            if not len(chunks):
                                continue
                            first_chunk = read_file(os.path.join(project_path, chapter, chunks[0]))
                            usfm += "\n\n"
                            if '\\c {0}'.format(chapter_num) not in first_chunk:
                                usfm += "\\c {0}\n".format(chapter_num)
                            if os.path.isfile(os.path.join(project_path, chapter, 'title.txt')):
                                translated_title = read_file(os.path.join(project_path, chapter, 'title.txt'))
                                book_name = re.sub(r' \d+$', '', translated_title).strip()
                                if book_name.lower() != title.lower():
                                    usfm += "\cl {0}\n".format(translated_title)
                            for chunk in chunks:
                                if chunk in self.ignoreFiles:
                                    continue
                                chunk_num = os.path.splitext(chunk)[0].lstrip('0')
                                chunk_content = read_file(os.path.join(project_path, chapter, chunk))
                                if '\\v {0} '.format(chunk_num) not in chunk_content:
                                    chunk_content = '\\v {0} '.format(chunk_num) + chunk_content
                                usfm += chunk_content+"\n"
                        if project.identifier.lower() in BOOK_NUMBERS:
                            filename = file_format.format(BOOK_NUMBERS[project.identifier.lower()],
                                                          project.identifier.upper())
                        else:
                            filename = file_format.format(str(idx + 1).zfill(2), project.identifier.upper())
                        write_file(os.path.join(self.output_dir, filename), usfm)
                        self.books.append(filename)
        return True


class TaPreprocessor(Preprocessor):
    manual_title_map = {
        'checking': 'Checking Manual',
        'intro': 'Introduction to translationAcademy',
        'process': 'Process Manual',
        'translate': 'Translation Manual'
    }

    def __init__(self, *args, **kwargs):
        super(TaPreprocessor, self).__init__(*args, **kwargs)
        self.section_container_id = 1

    def get_title(self, project, link, alt_title=None):
        proj = None
        if link in project.config():
            proj = project
        else:
            for p in self.rc.projects:
                if link in p.config():
                    proj = p
        if proj:
            title_file = os.path.join(self.source_dir, proj.path, link, 'title.md')
            if os.path.isfile(title_file):
                return read_file(title_file)
        if alt_title:
            return alt_title
        else:
            return link.replace('-', ' ').title()

    def get_ref(self, project, link):
        if link in project.config():
            return '#{0}'.format(link)
        for p in self.rc.projects:
            if link in p.config():
                return '{0}.html#{1}'.format(p.identifier, link)
        return '#{0}'.format(link)

    def get_question(self, project, slug):
        subtitle_file = os.path.join(self.source_dir, project.path, slug, 'sub-title.md')
        if os.path.isfile(subtitle_file):
            return read_file(subtitle_file)

    def get_content(self, project, slug):
        content_file = os.path.join(self.source_dir, project.path, slug, '01.md')
        if os.path.isfile(content_file):
            return read_file(content_file)

    def compile_section(self, project, section, level):
        """
        Recursive section markdown creator

        :param project: 
        :param dict section: 
        :param int level: 
        :return: 
        """
        if 'link' in section:
            link = section['link']
        else:
            link = 'section-container-{0}'.format(self.section_container_id)
            self.section_container_id = self.section_container_id + 1
        markdown = '{0} <a id="{1}"/>{2}\n\n'.format('#' * level, link, self.get_title(project, link, section['title']))
        if 'link' in section:
            top_box = ""
            bottom_box = ""
            question = self.get_question(project, link)
            if question:
                top_box += 'This page answers the question: *{0}*\n\n'.format(question)
            config = project.config()
            if link in config:
                if 'dependencies' in config[link] and config[link]['dependencies']:
                    top_box += 'In order to understand this topic, it would be good to read:\n\n'
                    for dependency in config[link]['dependencies']:
                        top_box += '  * *[{0}]({1})*\n'.\
                            format(self.get_title(project, dependency), self.get_ref(project, dependency))
                if 'recommended' in config[link] and config[link]['recommended']:
                    bottom_box += 'Next we recommend you learn about:\n\n'
                    for recommended in config[link]['recommended']:
                        bottom_box += '  * *[{0}]({1})*\n'.\
                            format(self.get_title(project, recommended), self.get_ref(project, recommended))
            if top_box:
                markdown += '<div class="top-box box" markdown="1">\n{0}\n</div>\n\n'.format(top_box)
            content = self.get_content(project, link)
            if content:
                markdown += '{0}\n\n'.format(content)
            if bottom_box:
                markdown += '<div class="bottom-box box" markdown="1">\n{0}\n</div>\n\n'.format(bottom_box)
            markdown += '---\n\n'  # horizontal rule
        if 'sections' in section:
            for subsection in section['sections']:
                markdown += self.compile_section(project, subsection, level + 1)
        return markdown

    def run(self):
        for idx, project in enumerate(self.rc.projects):
            self.section_container_id = 1
            toc = self.rc.toc(project.identifier)
            if project.identifier in self.manual_title_map:
                title = self.manual_title_map[project.identifier]
            else:
                title = '{0} Manual'.format(project.identifier.title())
            markdown = '# {0}\n\n'.format(title)
            for section in toc['sections']:
                markdown += self.compile_section(project, section, 2)
            markdown = self.fix_links(markdown)
            output_file = os.path.join(self.output_dir, '{0}-{1}.md'.format(str(idx+1).zfill(2), project.identifier))
            write_file(output_file, markdown)

            # Copy the toc and config.yaml file to the output dir so they can be used to
            # generate the ToC on live.door43.org
            toc_file = os.path.join(self.source_dir, project.path, 'toc.yaml')
            if os.path.isfile(toc_file):
                copy(toc_file, os.path.join(self.output_dir, '{0}-{1}-toc.yaml'.format(str(idx+1).zfill(2),
                                                                                       project.identifier)))
            config_file = os.path.join(self.source_dir, project.path, 'config.yaml')
            if os.path.isfile(config_file):
                copy(config_file, os.path.join(self.output_dir, '{0}-{1}-config.yaml'.format(str(idx+1).zfill(2),
                                                                                             project.identifier)))
        return True

    def fix_links(self, content):
        # convert RC links, e.g. rc://en/tn/help/1sa/16/02 => https://git.door43.org/Door43/en_tn/1sa/16/02.md
        content = re.sub(r'rc://([^/]+)/([^/]+)/([^/]+)/([^\s\p{P})\]\n$]+)',
                         r'https://git.door43.org/Door43/\1_\2/src/master/\4.md', content, flags=re.IGNORECASE)
        # fix links to other sections within the same manual (only one ../ and a section name)
        # e.g. [Section 2](../section2/01.md) => [Section 2](#section2)
        content = re.sub(r'\]\(\.\./([^/)]+)/01.md\)', r'](#\1)', content)
        # fix links to other manuals (two ../ and a manual name and a section name)
        # e.g. [how to translate](../../translate/accurate/01.md) => [how to translate](translate.html#accurate)
        for idx, project in enumerate(self.rc.projects):
            pattern = re.compile(r'\]\(\.\./\.\./{0}/([^/)]+)/01.md\)'.format(project.identifier))
            replace = r']({0}-{1}.html#\1)'.format(str(idx+1).zfill(2), project.identifier)
            content = re.sub(pattern, replace, content)
        # fix links to other sections that just have the section name but no 01.md page (preserve http:// links)
        # e.g. See [Verbs](figs-verb) => See [Verbs](#figs-verb)
        content = re.sub(r'\]\(([^# :/)]+)\)', r'](#\1)', content)
        # convert URLs to links if not already
        content = re.sub(r'([^"(])((http|https|ftp)://[A-Z0-9/?&_.:=#-]+[A-Z0-9/?&_:=#-])', r'\1[\2](\2)',
                         content, flags=re.IGNORECASE)
        # URLS wth just www at the start, no http
        content = re.sub(r'([^A-Z0-9"(/])(www\.[A-Z0-9/?&_.:=#-]+[A-Z0-9/?&_:=#-])', r'\1[\2](http://\2)',
                         content, flags=re.IGNORECASE)
        return content


class TqPreprocessor(Preprocessor):
    sections = [
        {'book': "00-toc", 'title': 'Table of Contents'},
        {'book': "01-GEN", 'title': 'Genesis'},
        {'book': "02-EXO", 'title': 'Exodus'},
        {'book': "03-LEV", 'title': 'Leviticus'},
        {'book': "04-NUM", 'title': 'Numbers'},
        {'book': "05-DEU", 'title': 'Deuteronomy'},
        {'book': "06-JOS", 'title': 'Joshua'},
        {'book': "07-JDG", 'title': 'Judges'},
        {'book': "08-RUT", 'title': 'Ruth'},
        {'book': "09-1SA", 'title': '1 Samuel'},
        {'book': "10-2SA", 'title': '2 Samuel'},
        {'book': "11-1KI", 'title': '1 Kings'},
        {'book': "12-2KI", 'title': '2 Kings'},
        {'book': "13-1CH", 'title': '1 Chronicles'},
        {'book': "14-2CH", 'title': '2 Chronicles'},
        {'book': "15-EZR", 'title': 'Ezra'},
        {'book': "16-NEH", 'title': 'Nehemiah'},
        {'book': "17-EST", 'title': 'Esther'},
        {'book': "18-JOB", 'title': 'Job'},
        {'book': "19-PSA", 'title': 'Psalms'},
        {'book': "20-PRO", 'title': 'Proverbs'},
        {'book': "21-ECC", 'title': 'Ecclesiastes'},
        {'book': "22-SNG", 'title': 'Song of Solomon'},
        {'book': "23-ISA", 'title': 'Isaiah'},
        {'book': "24-JER", 'title': 'Jeremiah'},
        {'book': "25-LAM", 'title': 'Lamentations'},
        {'book': "26-EZK", 'title': 'Ezekiel'},
        {'book': "27-DAN", 'title': 'Daniel'},
        {'book': "28-HOS", 'title': 'Hosea'},
        {'book': "29-JOL", 'title': 'Joel'},
        {'book': "30-AMO", 'title': 'Amos'},
        {'book': "31-OBA", 'title': 'Obadiah'},
        {'book': "32-JON", 'title': 'Jonah'},
        {'book': "33-MIC", 'title': 'Micah'},
        {'book': "34-NAM", 'title': 'Nahum'},
        {'book': "35-HAB", 'title': 'Habakkuk'},
        {'book': "36-ZEP", 'title': 'Zephaniah'},
        {'book': "37-HAG", 'title': 'Haggai'},
        {'book': "38-ZEC", 'title': 'Zechariah'},
        {'book': "39-MAL", 'title': 'Malachi'},
        {'book': "41-MAT", 'title': 'Matthew'},
        {'book': "42-MRK", 'title': 'Mark'},
        {'book': "43-LUK", 'title': 'Luke'},
        {'book': "44-JHN", 'title': 'John'},
        {'book': "45-ACT", 'title': 'Acts'},
        {'book': "46-ROM", 'title': 'Romans'},
        {'book': "47-1CO", 'title': '1 Corinthians'},
        {'book': "48-2CO", 'title': '2 Corinthians'},
        {'book': "49-GAL", 'title': 'Galatians'},
        {'book': "50-EPH", 'title': 'Ephesians'},
        {'book': "51-PHP", 'title': 'Philippians'},
        {'book': "52-COL", 'title': 'Colossians'},
        {'book': "53-1TH", 'title': '1 Thessalonians'},
        {'book': "54-2TH", 'title': '2 Thessalonians'},
        {'book': "55-1TI", 'title': '1 Timothy'},
        {'book': "56-2TI", 'title': '2 Timothy'},
        {'book': "57-TIT", 'title': 'Titus'},
        {'book': "58-PHM", 'title': 'Philemon'},
        {'book': "59-HEB", 'title': 'Hebrews'},
        {'book': "60-JAS", 'title': 'James'},
        {'book': "61-1PE", 'title': '1 Peter'},
        {'book': "62-2PE", 'title': '2 Peter'},
        {'book': "63-1JN", 'title': '1 John'},
        {'book': "64-2JN", 'title': '2 John'},
        {'book': "65-3JN", 'title': '3 John'},
        {'book': "66-JUD", 'title': 'Jude'},
        {'book': "67-REV", 'title': 'Revelation'},
    ]

    def __init__(self, *args, **kwargs):
        super(TqPreprocessor, self).__init__(*args, **kwargs)
        self.section_container_id = 1
        self.toc = ''
        self.index_json = None
        self.section_header_marker = '###############'

    def mark_chapter(self, ident, chapter, text):
        a = '{0} {1}\n\n'.format(self.section_header_marker, chapter)  # put in invalid header for section - we will correct heading level later
        return text + a

    def mark_chunk(self, ident, chapter, chunk, text):
        chunk_marker = os.path.splitext(chunk)[0]
        a = '{0}# {1}:{2}\n\n'.format(self.section_header_marker, chapter, chunk_marker)  # put in invalid header for section - we will correct heading level later
        return text + a

    def compile_section(self, title, link, content):
        """
        Recursive section markdown creator

        :param content:
        :param link:
        :param title:
        :return:
        """
        level = 3
        markdown = ''
        level_increase = ('#' * level)
        markdown += '{0} <a id="{1}"/>{2}\n\n'.format('#' * (level-2), link, title)  # add book title
        content = content.replace('\r', '')
        lines = content.split('\n')
        section_header_length = len(self.section_header_marker)
        for i in range(0, len(lines)):
            line = lines[i]
            if line[:section_header_length] == self.section_header_marker:
                text = line[section_header_length:]
                if text[0] == '#':  # check if chunk marker
                    line = level_increase + ' ' + title + text[1:]  # fix header level and add title
                else:  # chapter marker
                    line = '#' * (level-1) + ' ' + title + text  # fix header level and add title
                lines[i] = line
            elif line and (line[0] == '#'):
                if line.rstrip()[-1] == '#':
                    line = level_increase + line.rstrip() + level_increase
                else:
                    line = level_increase + line
                lines[i] = line
        content = '\n'.join(lines)
        markdown += content + '\n\n---\n\n'  # horizontal rule
        return markdown

    def run(self):
        super(TqPreprocessor, self).run()
        self.toc = None
        projects = {}
        self.index_json = {
            'titles': {},
            'chapters': {},
            'book_codes': {}
        }
        for idx, project in enumerate(self.rc.projects):
            section = self.get_section_for_file(project.identifier)
            if section:
                link = self.get_link_for_section(section)
                book = section['book']
                if not self.toc:
                    self.toc = '# Table of Contents:\n\n'
                projects[book] = {
                    'link': link,
                }
            else:
                App.logger.debug('TqPreprocessor: extra project found: {0}'.format(project.identifier))

        for section in TqPreprocessor.sections:  # index by book order
            book = section['book']
            if book in projects:
                file = os.path.join(self.output_dir, book + '.md')
                link = self.get_link_for_section(section)
                book = section['book']
                title = section['title']
                if not os.path.exists(file):
                    App.logger.debug('TqPreprocessor: book missing: {0}'.format(book))
                    continue
                initial_markdown = read_file(file)
                markdown = self.compile_section(title, link, initial_markdown)
                markdown = self.fix_links(markdown, book)
                if initial_markdown != markdown:
                    write_file(file, markdown)
                self.toc += '* [{1}](./{0}.html)\n'.format(book, title)
                self.index_json['titles'][book + '.html'] = title
            else:
                App.logger.debug('TqPreprocessor: missing book: {0}'.format(book))

        self.toc = self.fix_links(self.toc, '-')
        output_file = os.path.join(self.output_dir, '00-toc.md')
        write_file(output_file, self.toc)
        self.index_json['titles']['00-toc.html'] = 'Table of Contents'
        output_file = os.path.join(self.output_dir, 'index.json')
        write_file(output_file, self.index_json)

        # Copy the toc and config.yaml file to the output dir so they can be used to
        # generate the ToC on live.door43.org
        toc_file = os.path.join(self.source_dir, project.path, 'toc.yaml')
        if os.path.isfile(toc_file):
            copy(toc_file, os.path.join(self.output_dir, 'toc.yaml'))
        config_file = os.path.join(self.source_dir, project.path, 'config.yaml')
        if os.path.isfile(config_file):
            copy(config_file, os.path.join(self.output_dir, 'config.yaml'))
        return True

    def fix_links(self, content, section_link):
        if not content:
            return content

        # convert RC links, e.g. rc://en/tn/help/1sa/16/02 => https://git.door43.org/Door43/en_tn/1sa/16/02.md
        content = re.sub(r'rc://([^/]+)/([^/]+)/([^/]+)/([^\s)\]\n$]+)',
                         r'https://git.door43.org/{0}/\1_\2/src/master/\4.md'.format(self.rc.repo_name), content,
                         flags=re.IGNORECASE)
        # fix links to other sections within the same manual (only one ../ and a section name that matches section_link)
        # e.g. [covenant](../kt/covenant.md) => [covenant](#covenant)
        pattern = r'\]\(\.\.\/{0}\/([^/]+).md\)'.format(section_link)
        content = re.sub(pattern, r'](#\1)', content)
        # fix links to other sections within the same manual (only one ../ and a section name)
        # e.g. [commit](../other/commit.md) => [commit](other.html#commit)
        for section in TqPreprocessor.sections:
            link = self.get_link_for_section(section)
            pattern = re.compile(r'\]\(\.\./{0}/([^/]+).md\)'.format(link))
            replace = r']({0}.html#\1)'.format(link)
            content = re.sub(pattern, replace, content)
        # fix links to other sections that just have the section name but no 01.md page (preserve http:// links)
        # e.g. See [Verbs](figs-verb) => See [Verbs](#figs-verb)
        content = re.sub(r'\]\(([^# :/)]+)\)', r'](#\1)', content)
        # convert URLs to links if not already
        content = re.sub(r'([^"(])((http|https|ftp)://[A-Z0-9/?&_.:=#-]+[A-Z0-9/?&_:=#-])', r'\1[\2](\2)',
                         content, flags=re.IGNORECASE)
        # URLS wth just www at the start, no http
        content = re.sub(r'([^A-Z0-9"(/])(www\.[A-Z0-9/?&_.:=#-]+[A-Z0-9/?&_:=#-])', r'\1[\2](http://\2)',
                         content, flags=re.IGNORECASE)
        return content

    def get_section_for_file(self, id):
        id = id.lower()
        for section in TqPreprocessor.sections:
            if (id == section['book'].lower()) or (id == self.get_link_for_section(section)):
                return section
        return None

    def get_link_for_section(self, section):
        link = section['book']
        parts = link.split('-')
        if len(parts) > 1:
            link = parts[1].lower()
        return link


class TwPreprocessor(Preprocessor):
    sections = [
        {'link': 'kt', 'title': 'Key Terms'},
        {'link': 'names', 'title': 'Names'},
        {'link': 'other', 'title': 'Other'}
    ]

    def __init__(self, *args, **kwargs):
        super(TwPreprocessor, self).__init__(*args, **kwargs)
        self.section_container_id = 1
        self.toc = ''
        self.index_json = None

    def get_title(self, project, alt_title=None):
        title = alt_title
        return title.title()

    def get_content(self, content_file):
        if os.path.isfile(content_file):
            return read_file(content_file)

    def compile_section(self, project, section, level):
        """
        Recursive section markdown creator

        :param project:
        :param dict section:
        :param int level:
        :return:
        """
        if 'link' in section:
            link = section['link']
        else:
            return ''
        title = self.get_title(project, section['title'])
        markdown = ''
        if 'link' in section:
            level_increase = ('#' * level)
            files = sorted(glob(os.path.join(self.source_dir, project.path, link, '*.md')))
            if files:
                markdown += '{0} <a id="{1}"/>{2}\n\n'.format('#' * level, link, title)
                self.toc += '### {0}:\n\n'.format(title)
                for file in files:
                    top_box = ""
                    if top_box:
                        markdown += '<div class="top-box box" markdown="1">\n{0}\n</div>\n\n'.format(top_box)
                    content = self.get_content(file)
                    content = content.replace('\r', '')
                    lines = content.split('\n')
                    for i in range(0, len(lines)):
                        line = lines[i]
                        if line and (line[0] == '#'):
                            line = level_increase + line.rstrip() + level_increase
                            lines[i] = line
                    content = '\n'.join(lines)
                    if content:
                        file_name = os.path.basename(file)
                        anchor = os.path.splitext(file_name)[0]
                        markdown += '<a id="{0}"/>\n\n{1}\n\n'.format(anchor, content)
                        self.toc += '* [{1}]({0}.html#{1})\n'.format(link, anchor)

                    markdown += '---\n\n'  # horizontal rule

        return markdown

    def run(self):
        self.index_json = {
            'titles': {},
            'chapters': {},
            'book_codes': {}
        }

        for idx, project in enumerate(self.rc.projects):
            self.section_container_id = 1
            title = project.title
            self.toc = '# {0}\n\n'.format(title)
            self.toc += '## Table of Contents:\n\n'
            for section in TwPreprocessor.sections:
                markdown = '# {0}\n\n'.format(title)
                section_md = self.compile_section(project, section, 2)
                if not section_md:
                    continue
                markdown += section_md
                markdown = self.fix_links(markdown, section['link'])
                output_file = os.path.join(self.output_dir, '{0}.md'.format(section['link']))
                write_file(output_file, markdown)
                self.index_json['titles'][section['link'] + '.html'] = section['title']

            self.toc = self.fix_links(self.toc, '-')
            output_file = os.path.join(self.output_dir, '0toc.md')
            write_file(output_file, self.toc)
            self.index_json['titles']['0toc.html'] = 'Table of Contents'
            output_file = os.path.join(self.output_dir, 'index.json')
            write_file(output_file, self.index_json)

            # Copy the toc and config.yaml file to the output dir so they can be used to
            # generate the ToC on live.door43.org
            toc_file = os.path.join(self.source_dir, project.path, 'toc.yaml')
            if os.path.isfile(toc_file):
                copy(toc_file, os.path.join(self.output_dir, 'toc.yaml'))
            config_file = os.path.join(self.source_dir, project.path, 'config.yaml')
            if os.path.isfile(config_file):
                copy(config_file, os.path.join(self.output_dir, 'config.yaml'))
        return True

    def fix_links(self, content, section_link):
        # convert RC links, e.g. rc://en/tn/help/1sa/16/02 => https://git.door43.org/Door43/en_tn/1sa/16/02.md
        content = re.sub(r'rc://([^/]+)/([^/]+)/([^/]+)/([^\s)\]\n$]+)',
                         r'https://git.door43.org/{0}/\1_\2/src/master/\4.md'.format(self.rc.repo_name), content,
                         flags=re.IGNORECASE)
        # fix links to other sections within the same manual (only one ../ and a section name that matches section_link)
        # e.g. [covenant](../kt/covenant.md) => [covenant](#covenant)
        pattern = r'\]\(\.\.\/{0}\/([^/]+).md\)'.format(section_link)
        content = re.sub(pattern, r'](#\1)', content)
        # fix links to other sections within the same manual (only one ../ and a section name)
        # e.g. [commit](../other/commit.md) => [commit](other.html#commit)
        for section in TwPreprocessor.sections:
            link_ = section['link']
            pattern = re.compile(r'\]\(\.\./{0}/([^/]+).md\)'.format(link_))
            replace = r']({0}.html#\1)'.format(link_)
            content = re.sub(pattern, replace, content)
        # fix links to other sections that just have the section name but no 01.md page (preserve http:// links)
        # e.g. See [Verbs](figs-verb) => See [Verbs](#figs-verb)
        content = re.sub(r'\]\(([^# :/)]+)\)', r'](#\1)', content)
        # convert URLs to links if not already
        content = re.sub(r'([^"(])((http|https|ftp)://[A-Z0-9/?&_.:=#-]+[A-Z0-9/?&_:=#-])', r'\1[\2](\2)',
                         content, flags=re.IGNORECASE)
        # URLS wth just www at the start, no http
        content = re.sub(r'([^A-Z0-9"(/])(www\.[A-Z0-9/?&_.:=#-]+[A-Z0-9/?&_:=#-])', r'\1[\2](http://\2)',
                         content, flags=re.IGNORECASE)
        return content
