import re
import os
import codecs

from .errors import MalformedFileError, MalformedCaptionError
from .structures import Block, Style, Caption


class TextBasedParser(object):
    """
    Parser for plain text caption files.
    This is a generic class, do not use directly.
    """

    TIMEFRAME_LINE_PATTERN = ''
    PARSER_OPTIONS = {}

    def __init__(self, parse_options=None):
        self.captions = []
        self.parse_options = parse_options or {}

    def read(self, file):
        """Reads the captions file."""
        content = self._get_content_from_file(file_path=file)
        self._validate(content)
        self._parse(content)

        return self

    def read_from_buffer(self, buffer):
        content = self._read_content_lines(buffer)
        self._validate(content)
        self._parse(content)

        return self

    def _get_content_from_file(self, file_path):
        encoding = self._read_file_encoding(file_path)
        with open(file_path, encoding=encoding) as f:
            return self._read_content_lines(f)

    def _read_file_encoding(self, file_path):
        first_bytes = min(32, os.path.getsize(file_path))
        with open(file_path, 'rb') as f:
            raw = f.read(first_bytes)

        if raw.startswith(codecs.BOM_UTF8):
            return 'utf-8-sig'
        else:
            return 'utf-8'

    def _read_content_lines(self, file_obj):

        lines = [line.rstrip('\n') for line in file_obj.readlines()]

        if not lines:
            raise MalformedFileError('The file is empty.')

        return lines

    def _read_content(self, file):
        return self._get_content_from_file(file_path=file)

    def _parse_timeframe_line(self, line):
        """Parse timeframe line and return start and end timestamps."""
        tf = self._validate_timeframe_line(line)
        if not tf:
            raise MalformedCaptionError('Invalid time format')

        return tf.group(1), tf.group(2)

    def _validate_timeframe_line(self, line):
        return re.match(self.TIMEFRAME_LINE_PATTERN, line)

    def _is_timeframe_line(self, line):
        """
        This method returns True if the line contains the timeframes.
        To be implemented by child classes.
        """
        raise NotImplementedError

    def _validate(self, lines):
        """
        Validates the format of the parsed file.
        To be implemented by child classes.
        """
        raise NotImplementedError

    def _should_skip_line(self, line, index, caption):
        """
        This method returns True for a line that should be skipped.
        Implement in child classes if needed.
        """
        return False

    def _parse(self, lines):
        self.captions = []
        c = None

        for index, line in enumerate(lines):
            if self._is_timeframe_line(line):
                try:
                    start, end = self._parse_timeframe_line(line)
                except MalformedCaptionError as e:
                    raise MalformedCaptionError('{} in line {}'.format(e, index + 1))
                c = Caption(start, end)
            elif self._should_skip_line(line, index, c):  # allow child classes to skip lines based on the content
                continue
            elif line:
                if c is None:
                    raise MalformedCaptionError(
                        'Caption missing timeframe in line {}.'.format(index + 1))
                else:
                    c.add_line(line)
            else:
                if c is None:
                    continue
                if not c.lines:
                    if self.PARSER_OPTIONS.get('ignore_empty_captions', False):
                        c = None
                        continue
                    raise MalformedCaptionError('Caption missing text in line {}.'.format(index + 1))

                self.captions.append(c)
                c = None

        if c is not None and c.lines:
            self.captions.append(c)





class WebVTTParserCDP(TextBasedParser):
    """
    WebVTT parser for cdp.
    
    Group Sentences together.
    
    """
    TIMEFRAME_LINE_PATTERN = re.compile('\s*((?:\d+:)?\d{2}:\d{2}.\d{3})\s*-->\s*((?:\d+:)?\d{2}:\d{2}.\d{3})')
    COMMENT_PATTERN = re.compile('NOTE(?:\s.+|$)')
    STYLE_PATTERN = re.compile('STYLE[ \t]*$')
    IDENTIFY_SENTENCE = re.compile(r'.*[.!?]' )  

    
    def __init__(self):
        super().__init__()
        self.styles = []

    # Group Sentences
    def _group_by_sentence(self, line):
        return re.match(self.IDENTIFY_SENTENCE, line)
    
    
    def _compute_blocks(self, lines):
        blocks = []

        for index, line in enumerate(lines, start=1):
            if line:
                if not blocks:
                    blocks.append(Block(index))
                if not blocks[-1].lines:
                    blocks[-1].line_number = index
                blocks[-1].lines.append(line)
            else:
                blocks.append(Block(index))

        # filter out empty blocks and skip signature
        self.blocks = list(filter(lambda x: x.lines, blocks))[1:]

    def _parse_cue_block(self, block):
        caption = Caption()
        cue_timings = None

        for line_number, line in enumerate(block.lines):
            if self._is_cue_timings_line(line):
                if cue_timings is None:
                    try:
                        cue_timings = self._parse_timeframe_line(line)
                    except MalformedCaptionError as e:
                        raise MalformedCaptionError(
                            '{} in line {}'.format(e, block.line_number + line_number))
                else:
                    raise MalformedCaptionError(
                        '--> found in line {}'.format(block.line_number + line_number))
            elif line_number == 0:
                caption.identifier = line
            else:
                if self._group_by_sentence(line):
                    caption.flagEndSentence = True
                caption.add_line(line)

        caption.start = cue_timings[0]
        caption.end = cue_timings[1]
        return caption
    

    def _parse(self, lines):
        self.captions = []
        self._compute_blocks(lines)
        group_captions = ""
        caption = None
        start_time ='00:00:00.000'
        
        for block in self.blocks:
            
            if self._is_cue_block(block):
                caption = self._parse_cue_block( block )
                
                # Begining of sentence so grab start
                if group_captions == "":
                    start_time = caption.start
                    
                group_captions += " " + caption.text
                
                
                # if it is the end of a sentence group
                if caption.flagEndSentence:
                    #add all the sub captions
                    caption.text = group_captions
                    group_captions = ""
                    
                    # finished grouping so make sure to update the 
                    caption.start = start_time
                    self.captions.append(caption)

                     
                
                    
                
            elif self._is_comment_block(block):
                continue
            
            elif self._is_style_block(block):
                if self.captions:
                    raise MalformedFileError(
                        'Style block defined after the first cue in line {}.'
                        .format(block.line_number))
                style = Style()
                style.lines = block.lines[1:]
                self.styles.append(style)
                
            else:
                if len(block.lines) == 1:
                    raise MalformedCaptionError(
                        'Standalone cue identifier in line {}.'.format(block.line_number))
                else:
                    raise MalformedCaptionError(
                        'Missing timing cue in line {}.'.format(block.line_number+1))


    def _validate(self, lines):
        if not re.match('WEBVTT', lines[0]):
            raise MalformedFileError('The file does not have a valid format')

    def _is_cue_timings_line(self, line):
        return '-->' in line

    def _is_cue_block(self, block):
        """Returns True if it is a cue block
        (one of the two first lines being a cue timing line)"""
        return any(map(self._is_cue_timings_line, block.lines[:2]))

    def _is_comment_block(self, block):
        """Returns True if it is a comment block"""
        return re.match(self.COMMENT_PATTERN, block.lines[0])

    def _is_style_block(self, block):
        """Returns True if it is a style block"""
        return re.match(self.STYLE_PATTERN, block.lines[0])
    
    




class SRTParser(TextBasedParser):
    """
    SRT parser.
    """

    TIMEFRAME_LINE_PATTERN = re.compile('\s*(\d+:\d{2}:\d{2},\d{3})\s*-->\s*(\d+:\d{2}:\d{2},\d{3})')

    PARSER_OPTIONS = {
        'ignore_empty_captions': True
    }

    def _validate(self, lines):
        if len(lines) < 2 or lines[0] != '1' or not self._validate_timeframe_line(lines[1]):
            raise MalformedFileError('The file does not have a valid format.')

    def _is_timeframe_line(self, line):
        return '-->' in line

    def _should_skip_line(self, line, index, caption):
        return caption is None and line.isdigit()


class WebVTTParser(TextBasedParser):
    """
    WebVTT parser.
    """

    TIMEFRAME_LINE_PATTERN = re.compile('\s*((?:\d+:)?\d{2}:\d{2}.\d{3})\s*-->\s*((?:\d+:)?\d{2}:\d{2}.\d{3})')
    COMMENT_PATTERN = re.compile('NOTE(?:\s.+|$)')
    STYLE_PATTERN = re.compile('STYLE[ \t]*$')

    def __init__(self):
        super().__init__()
        self.styles = []

    def _compute_blocks(self, lines):
        blocks = []

        for index, line in enumerate(lines, start=1):
            if line:
                if not blocks:
                    blocks.append(Block(index))
                if not blocks[-1].lines:
                    blocks[-1].line_number = index
                blocks[-1].lines.append(line)
            else:
                blocks.append(Block(index))

        # filter out empty blocks and skip signature
        self.blocks = list(filter(lambda x: x.lines, blocks))[1:]

    def _parse_cue_block(self, block):
        caption = Caption()
        cue_timings = None

        for line_number, line in enumerate(block.lines):
            if self._is_cue_timings_line(line):
                if cue_timings is None:
                    try:
                        cue_timings = self._parse_timeframe_line(line)
                    except MalformedCaptionError as e:
                        raise MalformedCaptionError(
                            '{} in line {}'.format(e, block.line_number + line_number))
                else:
                    raise MalformedCaptionError(
                        '--> found in line {}'.format(block.line_number + line_number))
            elif line_number == 0:
                caption.identifier = line
            else:
                caption.add_line(line)

        caption.start = cue_timings[0]
        caption.end = cue_timings[1]
        return caption

    def _parse(self, lines):
        self.captions = []
        self._compute_blocks(lines)

        for block in self.blocks:
            if self._is_cue_block(block):
                caption = self._parse_cue_block(block)
                self.captions.append(caption)
            elif self._is_comment_block(block):
                continue
            elif self._is_style_block(block):
                if self.captions:
                    raise MalformedFileError(
                        'Style block defined after the first cue in line {}.'
                        .format(block.line_number))
                style = Style()
                style.lines = block.lines[1:]
                self.styles.append(style)
            else:
                if len(block.lines) == 1:
                    raise MalformedCaptionError(
                        'Standalone cue identifier in line {}.'.format(block.line_number))
                else:
                    raise MalformedCaptionError(
                        'Missing timing cue in line {}.'.format(block.line_number+1))

    def _validate(self, lines):
        if not re.match('WEBVTT', lines[0]):
            raise MalformedFileError('The file does not have a valid format')

    def _is_cue_timings_line(self, line):
        return '-->' in line

    def _is_cue_block(self, block):
        """Returns True if it is a cue block
        (one of the two first lines being a cue timing line)"""
        return any(map(self._is_cue_timings_line, block.lines[:2]))

    def _is_comment_block(self, block):
        """Returns True if it is a comment block"""
        return re.match(self.COMMENT_PATTERN, block.lines[0])

    def _is_style_block(self, block):
        """Returns True if it is a style block"""
        return re.match(self.STYLE_PATTERN, block.lines[0])


class SBVParser(TextBasedParser):
    """
    YouTube SBV parser.
    """

    TIMEFRAME_LINE_PATTERN = re.compile('\s*(\d+:\d{2}:\d{2}.\d{3}),(\d+:\d{2}:\d{2}.\d{3})')

    def _validate(self, lines):
        if not self._validate_timeframe_line(lines[0]):
            raise MalformedFileError('The file does not have a valid format')

    def _is_timeframe_line(self, line):
        return self._validate_timeframe_line(line)
