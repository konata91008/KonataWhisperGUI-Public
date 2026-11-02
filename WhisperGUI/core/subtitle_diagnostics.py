"""Offline, conservative SRT diagnostics. Never invent timing or discard text."""
import re
from dataclasses import dataclass, replace

from .chinese_conversion import MAX_TEXT_CHARS


class DiagnosticError(ValueError):
    """Stable, localizable error codes only."""


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    line: int
    cue: int = 0
    other: int = 0
    value: int = 0


@dataclass(frozen=True)
class Caption:
    index: int
    line: int
    timing_line: int
    number: str
    text: str
    start: int | None
    end: int | None
    suffix: str = ''


@dataclass(frozen=True)
class Report:
    captions: tuple
    issues: tuple

    @property
    def errors(self):
        return sum(issue.severity == 'error' for issue in self.issues)

    @property
    def warnings(self):
        return len(self.issues) - self.errors


@dataclass(frozen=True)
class RepairResult:
    original: Report
    checked: Report
    text: str


# Tolerate only unambiguous variants. Invalid ranges and unknown suffixes are
# errors, not silently coerced or stripped. Position extensions remain intact.
STAMP = r'([0-9]{1,6}):([0-9]{1,2}):([0-9]{1,2})[,.]([0-9]{1,3})'
TIME_LINE = re.compile(r'^[ \t]*' + STAMP + r'[ \t]*(?:-->|->|→)[ \t]*' + STAMP +
                       r'(?P<suffix>[ \t]+X1:[0-9]+[ \t]+X2:[0-9]+[ \t]+Y1:[0-9]+[ \t]+Y2:[0-9]+)?[ \t]*$')
NUMBER = re.compile(r'^[0-9]{1,9}$')
TIME_LIKE = re.compile(r'^[ \t]*-?[0-9]{1,6}:[^\n]*(?:--?>|→|⇒)')


def timestamp(milliseconds):
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}'


def parse_timing(line):
    match = TIME_LINE.fullmatch(line)
    if not match:
        return None
    values = []
    for offset in (0, 4):
        hour, minute, second, fraction = match.groups()[offset:offset + 4]
        if int(minute) > 59 or int(second) > 59:
            return None
        values.append((int(hour) * 3600 + int(minute) * 60 + int(second)) * 1000 + int(fraction.ljust(3, '0')))
    suffix = match.group('suffix') or ''
    return (*values, suffix)


def timing_text(caption):
    return f'{timestamp(caption.start)} --> {timestamp(caption.end)}{caption.suffix}'


def _segments(lines):
    """Recover clear headers without blank separators, with original line numbers.

    Unrecognizable blocks are retained for error reporting, never dropped.
    A timestamp-like line inside dialogue is deliberately flagged as ambiguous
    by the resulting checks instead of guessing timestamps from free text.
    """
    block = []
    for number, text in enumerate(lines + [''], 1):
        if text.strip():
            block.append((number, text))
            continue
        if not block:
            continue
        begin, cursor = 0, (2 if NUMBER.fullmatch(block[0][1].strip()) else 1)
        while cursor < len(block):
            numbered = (NUMBER.fullmatch(block[cursor][1].strip()) and cursor + 1 < len(block)
                        and (TIME_LIKE.match(block[cursor + 1][1]) or '-->' in block[cursor + 1][1]))
            bare_time = TIME_LIKE.match(block[cursor][1])
            if numbered or bare_time:
                yield block[begin:cursor], begin > 0
                begin = cursor
                cursor += 2 if numbered else 1
            else:
                cursor += 1
        yield block[begin:], begin > 0
        block = []


def analyze_srt(content):
    if len(content) > MAX_TEXT_CHARS:
        raise DiagnosticError('too_large')
    if not content.strip('\ufeff \r\n\t'):
        raise DiagnosticError('empty')
    content = content.removeprefix('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    lines = content.split('\n')
    captions, issues = [], []
    for block, missing_separator in _segments(lines):
        index, first_line = len(captions) + 1, block[0][0]
        number, timing_index = block[0][1].strip(), 1
        if TIME_LIKE.match(block[0][1]):
            number, timing_index = '', 0
        elif len(block) < 2 or not NUMBER.fullmatch(number):
            issues.append(Issue('unrecognized', 'error', first_line, index))
            # Continue scanning the remainder of the file after malformed blocks.
            continue
        if missing_separator:
            issues.append(Issue('separator', 'warning', first_line, index))
            if timing_index == 0:
                issues.append(Issue('ambiguous', 'error', first_line, index))
        if not number:
            issues.append(Issue('missing_number', 'warning', first_line, index))
        elif number != str(index):
            issues.append(Issue('numbering', 'warning', first_line, index, value=index))
        line, raw_timing = block[timing_index]
        parsed = parse_timing(raw_timing)
        text = '\n'.join(part[1] for part in block[timing_index + 1:])
        if not text.strip():
            issues.append(Issue('empty_caption', 'error', line, index))
        if any(ord(character) < 32 and character not in '\t\n' for character in text):
            issues.append(Issue('control', 'error', line + 1, index))
        start, end, suffix = parsed if parsed else (None, None, '')
        caption = Caption(index, first_line, line, number, text, start, end, suffix)
        captions.append(caption)
        if parsed is None:
            issues.append(Issue('invalid_time', 'error', line, index))
        elif end <= start:
            issues.append(Issue('duration', 'error', line, index))
        else:
            if raw_timing != timing_text(caption):
                issues.append(Issue('time_format', 'warning', line, index))
            if end - start < 100:
                issues.append(Issue('short', 'warning', line, index, value=end - start))
    valid = [cue for cue in captions if cue.start is not None and cue.end > cue.start]
    for previous, cue in zip(valid, valid[1:]):
        if cue.start < previous.start:
            issues.append(Issue('order', 'warning', cue.timing_line, cue.index, previous.index))
    # Track the furthest-ending interval, not just the preceding entry: nested
    # overlaps must still be detected after a short intervening caption ends.
    active = None
    for cue in sorted(valid, key=lambda cue: (cue.start, cue.index)):
        if active and cue.start < active.end:
            issues.append(Issue('overlap', 'warning', cue.timing_line, cue.index, active.index,
                                min(cue.end, active.end) - cue.start))
        if active is None or cue.end > active.end:
            active = cue
    return Report(tuple(captions), tuple(sorted(issues, key=lambda issue: (issue.line, issue.code))))


def repair_srt(content, *, sort_by_time=False, trim_overlaps=False):
    report = analyze_srt(content)
    if report.errors or not report.captions:
        raise DiagnosticError('manual_required')
    captions = list(report.captions)
    if sort_by_time:
        captions.sort(key=lambda cue: (cue.start, cue.index))
    if trim_overlaps:
        if any(a.start > b.start for a, b in zip(captions, captions[1:])):
            raise DiagnosticError('sort_required')
        for index in range(len(captions) - 1):
            cue, following = captions[index:index + 2]
            if cue.end > following.start:
                # Leave a 1 ms gap without moving any later caption. Equal
                # starts or intervals too narrow for a positive duration need
                # human review; never merge, delete, or shift the whole file.
                end = following.start - 1
                if end <= cue.start:
                    raise DiagnosticError('cannot_trim')
                captions[index] = replace(cue, end=end)
    output = '\n\n'.join(f'{index}\n{timing_text(cue)}\n{cue.text}'
                         for index, cue in enumerate(captions, 1)) + '\n\n'
    checked = analyze_srt(output)
    if checked.errors or (trim_overlaps and any(issue.code == 'overlap' for issue in checked.issues)):
        raise DiagnosticError('manual_required')
    return RepairResult(report, checked, output)
