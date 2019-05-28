import re


class Tag:
    def __init__(self, pattern, description, on_open, on_close):
        self.pattern = pattern
        self.description = description
        self.on_open = on_open
        self.on_close = on_close


class TagAdapter:
    md_tags = [
        Tag(
            pattern=re.compile(r"##\s*(?P<body>.*)"),
            description="Medium-sized text",
            on_open=lambda p: p.set_size("M"),
            on_close=lambda p: p.set_size("S"),
        ),
        Tag(
            pattern=re.compile(r"#\s*(?P<body>.*)"),
            description="Large-sized text",
            on_open=lambda p: p.set_size("L"),
            on_close=lambda p: p.set_size("S"),
        ),
        Tag(
            pattern=re.compile(r"\*\s*(?P<body>.*)"),
            description="Bold text",
            on_open=lambda p: p.bold_on(),
            on_close=lambda p: p.bold_off(),
        ),
        Tag(
            pattern=re.compile(r"~\s*(?P<body>.*?)~"),
            description="Inverse text",
            on_open=lambda p: p.inverse_on(),
            on_close=lambda p: p.inverse_off(),
        ),
    ]

    def __init__(self, printer):
        self.printer = printer

    @staticmethod
    def tag_match(line):
        matches = (
            (tag, tag.pattern.match(line))
            for tag in TagAdapter.md_tags
        )
        return next(((tag, match) for (tag, match) in matches if match is not None), None)

    def print(self, raw):
        for line in raw.splitlines():
            match_pair = TagAdapter.tag_match(line)
            if match_pair is not None:
                tag, match = match_pair
                tag.on_open(self.printer)
                self.printer.print(match.group("body"))
                self.printer.print("\n")
                tag.on_close(self.printer)
            else:
                self.printer.print(line)
                self.printer.print("\n")
