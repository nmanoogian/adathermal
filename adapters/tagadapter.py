import re


class Tag:
    def __init__(self, name, description, on_open, on_close):
        self.name = name
        self.description = description
        self.on_open = on_open
        self.on_close = on_close


class TagAdapter:
    tags = [
        Tag(
            name="m",
            description="Medium-sized text",
            on_open=lambda p: p.set_size("M"),
            on_close=lambda p: p.set_size("S"),
        ),
        Tag(
            name="l",
            description="Large-sized text",
            on_open=lambda p: p.set_size("L"),
            on_close=lambda p: p.set_size("S"),
        ),
        Tag(
            name="b",
            description="Bold text",
            on_open=lambda p: p.bold_on(),
            on_close=lambda p: p.bold_off(),
        ),
        Tag(
            name="i",
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
            (tag, re.match(r"\[{}\]\s*(?P<body>.*)".format(tag.name), line))
            for tag in TagAdapter.tags
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
